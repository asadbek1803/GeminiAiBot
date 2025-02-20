import asyncio
import os
from typing import Optional
import whisper
import google.generativeai as ai
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

# Initialize Whisper model (using small model for faster processing)
whisper_model = whisper.load_model("small")

router = Router()

# Session management
user_sessions = {}
user_last_request_time = {}

def get_keyboard(language):
    """Foydalanuvchi tiliga mos Reply tugmalarni qaytaradi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[language]["btn_new_chat"]), KeyboardButton(text=buttons[language]["btn_stop"])],
            [KeyboardButton(text=buttons[language]["btn_continue"]), KeyboardButton(text=buttons[language]["btn_change_lang"])]
        ],
        resize_keyboard=True
    )

# Supported languages
SUPPORTED_LANGUAGES = {
    "eng": "en",  # English
    "ru": "ru",   # Russian
    "uz": "uz",   # Uzbek
    "tr": "tr"    # Turkish
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
        """Transcribe voice to text"""
        try:
            # Get language code from supported languages
            lang_code = SUPPORTED_LANGUAGES.get(language, "en")
            
            result = whisper_model.transcribe(
                file_path,
                language=lang_code,
                fp16=False
            )
            return result["text"].strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
        finally:
            # Clean up the voice file immediately after transcription
            await VoiceProcessor.cleanup_files(file_path)

async def handle_rate_limit(telegram_id: int) -> bool:
    """Handle request rate limiting"""
    now = asyncio.get_event_loop().time()
    if telegram_id in user_last_request_time:
        if (now - user_last_request_time[telegram_id]) < 1.5:  # Increased to 1.5 seconds
            return True
    user_last_request_time[telegram_id] = now
    return False

@router.message(F.voice)
async def handle_voice(message: types.Message):
    """Handle voice messages"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "eng"
    
    # Session check
    if telegram_id not in user_sessions:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML
        )
        return
    
    # Rate limit check
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
        # Ensure cleanup happens even if an error occurs
        if voice_path:
            await VoiceProcessor.cleanup_files(voice_path)

async def process_message(message: types.Message, text: Optional[str] = None):
    """Process messages (both voice and text)"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "eng"
    
    session = user_sessions.get(telegram_id)
    if not session:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML
        )
        return
    
    # Message limit check
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
        
        await thinking_msg.delete()
        await message.answer(
            text=response.text,
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