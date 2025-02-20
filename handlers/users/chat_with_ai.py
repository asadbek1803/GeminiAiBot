import asyncio
import os
from typing import Optional
import whisper
import google.generativeai as ai
import speech_recognition as sr
import ffmpeg
import re
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums.parse_mode import ParseMode
from loader import bot, db
from data.config import API_KEY
from componets.messages import buttons, messages

# AI model configuration
ai.configure(api_key=API_KEY)
model = ai.GenerativeModel("gemini-pro")

# Initialize Whisper model
whisper_model = whisper.load_model("small")

router = Router()

# Session management
user_sessions = {}
user_last_request_time = {}

def get_keyboard(language):
    """Return Reply buttons matching user's language."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[language]["btn_new_chat"]), KeyboardButton(text=buttons[language]["btn_stop"])],
            [KeyboardButton(text=buttons[language]["btn_continue"]), KeyboardButton(text=buttons["btn_change_lang"])]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def format_text(text):
    """Convert text to HTML format"""
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]*)`", r"<code>\1</code>", text)
    return text

# Supported languages
SUPPORTED_LANGUAGES = {
    "eng": {"code": "en", "speech": "en-US"},
    "ru": {"code": "ru", "speech": "ru-RU"},
    "uz": {"code": "uz", "speech": "uz-UZ"},
    "tr": {"code": "tr", "speech": "tr-TR"}
}

class VoiceProcessor:
    """Voice processing helper class"""
    
    @staticmethod
    async def cleanup_files(*file_paths: str):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error cleaning up file {file_path}: {e}")

    @staticmethod
    async def transcribe_voice(file_path: str, language: str) -> Optional[str]:
        """Transcribe voice to text using both Whisper and Google Speech Recognition"""
        try:
            # First attempt with Whisper
            lang_code = SUPPORTED_LANGUAGES[language]["code"]
            result = whisper_model.transcribe(
                file_path,
                language=lang_code,
                fp16=False
            )
            text = result["text"].strip()
            
            # If Whisper fails or returns empty, try Google Speech Recognition
            if not text:
                wav_path = file_path.replace(".ogg", ".wav")
                
                # Convert to WAV using ffmpeg
                stream = ffmpeg.input(file_path)
                stream = ffmpeg.output(stream, wav_path)
                ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                
                # Use Google Speech Recognition
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(
                        audio_data, 
                        language=SUPPORTED_LANGUAGES[language]["speech"]
                    )
                
                await VoiceProcessor.cleanup_files(wav_path)
            
            return text
            
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
        finally:
            await VoiceProcessor.cleanup_files(file_path)

async def handle_rate_limit(telegram_id: int) -> bool:
    """Handle request rate limiting"""
    now = asyncio.get_event_loop().time()
    if telegram_id in user_last_request_time:
        if (now - user_last_request_time[telegram_id]) < 1.5:
            return True
    user_last_request_time[telegram_id] = now
    return False

@router.message(Command("chat"))
@router.message(lambda message: any(message.text == buttons[lang]["btn_new_chat"] for lang in ["uz", "ru", "eng"]))
async def start_chat(message: types.Message):
    """Start AI chatbot with user."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"

    if telegram_id not in user_sessions:
        user_sessions[telegram_id] = {
            "chat": model.start_chat(),
            "message_count": 0,
            "language": language
        }

    await message.answer(
        text=messages[language]["start"],
        parse_mode=ParseMode.HTML,
        reply_markup=get_keyboard(language)
    )

@router.message(Command("stop"))
async def stop_chat(message: types.Message):
    """Stop the chat session."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"

    if telegram_id in user_sessions:
        del user_sessions[telegram_id]
        await message.answer(
            text=messages[language]["stop"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
    else:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )

@router.message(F.voice)
async def handle_voice(message: types.Message):
    """Handle voice messages"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    if telegram_id not in user_sessions:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML
        )
        return
    
    if await handle_rate_limit(telegram_id):
        await message.answer(
            text=messages[language]["time_waiter"],
            parse_mode=ParseMode.HTML
        )
        return
    
    thinking_msg = await message.answer(
        text=messages[language]["voice_processing"],
        parse_mode=ParseMode.HTML
    )
    
    voice_path = None
    try:
        # Download voice file
        voice = await bot.get_file(message.voice.file_id)
        voice_path = f"temp_voice_{message.message_id}.ogg"
        await bot.download_file(voice.file_path, voice_path)
        
        # Transcribe voice
        voice_text = await VoiceProcessor.transcribe_voice(voice_path, language)
        
        if not voice_text:
            await thinking_msg.delete()
            await message.answer(
                text=messages[language]["voice_error"],
                parse_mode=ParseMode.HTML
            )
            return
        
        # Show transcribed text
        await message.answer(
            text=messages[language]["voice_recognized"].format(text=voice_text),
            parse_mode=ParseMode.HTML
        )
        
        # Process with AI
        await thinking_msg.delete()
        await process_message(message, voice_text)
        
    except Exception as e:
        await thinking_msg.delete()
        await message.answer(
            text=messages[language]["error"].format(error=str(e)),
            parse_mode=ParseMode.HTML
        )
    finally:
        if voice_path:
            await VoiceProcessor.cleanup_files(voice_path)

async def process_message(message: types.Message, text: Optional[str] = None):
    """Process messages (both voice and text)"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    session = user_sessions.get(telegram_id)
    if not session:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML
        )
        return
    
    if session["message_count"] >= 20:
        del user_sessions[telegram_id]
        await message.answer(
            text=messages[language]["limit_reached"],
            parse_mode=ParseMode.HTML
        )
        return
    
    thinking_msg = await message.answer(
        text=messages[language]["thinking"],
        parse_mode=ParseMode.HTML
    )
    
    try:
        input_text = text if text else message.text
        response = session["chat"].send_message(input_text)
        session["message_count"] += 1
        
        formatted_response = format_text(response.text)
        
        await thinking_msg.delete()
        await message.answer(
            text=formatted_response,
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
    except Exception as e:
        await thinking_msg.delete()
        await message.answer(
            text=messages[language]["error"].format(error=str(e)),
            parse_mode=ParseMode.HTML
        )

@router.message()
async def chat_with_ai(message: types.Message):
    """Handle text messages"""
    if await handle_rate_limit(message.from_user.id):
        return
    await process_message(message)