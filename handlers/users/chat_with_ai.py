import asyncio
import os
import json
from typing import Optional
from vosk import Model, KaldiRecognizer
import wave
import google.generativeai as ai

import re
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums.parse_mode import ParseMode
from loader import bot, db
from data.config import API_KEY
from componets.messages import buttons, messages

IS_LINUX = os.name == "posix"

# For OGG to WAV conversion
if not IS_LINUX:
    import imageio_ffmpeg as ffmpeg
else:
    import ffmpeg

# AI model configuration
ai.configure(api_key=API_KEY)
model = ai.GenerativeModel("gemini-pro")

# Vosk model path - you'll need to download the appropriate model
VOSK_MODEL_PATH = "vosk-model-small-en"

router = Router()

# Session management
user_sessions = {}
user_last_request_time = {}

def get_keyboard(language):
    """Return Reply buttons matching user's language."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[language]["btn_new_chat"]), KeyboardButton(text=buttons[language]["btn_stop"])],
            [KeyboardButton(text=buttons[language]["btn_continue"]), KeyboardButton(text=buttons[language]["btn_change_lang"])]
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

# Supported languages and their Vosk model mappings
SUPPORTED_LANGUAGES = {
    "eng": {"code": "en", "vosk_model": "vosk-model-small-en"},
    "ru": {"code": "ru", "vosk_model": "vosk-model-small-ru"},
    "uz": {"code": "uz", "vosk_model": "vosk-model-small-uz"},
    "tr": {"code": "tr", "vosk_model": "vosk-model-small-tr"}
}

class VoiceProcessor:
    """Voice processing helper class using Vosk"""
    _models = {}  # Cache for loaded models

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
    async def convert_ogg_to_wav(ogg_path: str) -> str:
        """Convert OGG to WAV format for Vosk processing"""
        wav_path = ogg_path.replace(".ogg", ".wav")
        
        # Convert to WAV using ffmpeg
        if IS_LINUX:
            stream = ffmpeg.input(ogg_path)
            stream = ffmpeg.output(stream, wav_path, ar='16000')
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        else:
            ffmpeg_cmd = ffmpeg.get_ffmpeg_exe()
            os.system(f'"{ffmpeg_cmd}" -i "{ogg_path}" -ar 16000 -ac 1 "{wav_path}" -y')
            
        return wav_path

    @classmethod
    async def get_vosk_model(cls, language: str):
        """Get or load Vosk model for specified language"""
        model_name = SUPPORTED_LANGUAGES[language]["vosk_model"]
        
        if model_name not in cls._models:
            try:
                cls._models[model_name] = Model(model_name)
            except Exception as e:
                print(f"Error loading Vosk model {model_name}: {e}")
                # Fallback to English model if the requested language model is unavailable
                fallback_model = "vosk-model-small-en"
                if fallback_model not in cls._models:
                    cls._models[fallback_model] = Model(fallback_model)
                return cls._models[fallback_model]
                
        return cls._models[model_name]

    @classmethod
    async def transcribe_voice(cls, file_path: str, language: str) -> Optional[str]:
        """Transcribe voice to text using Vosk"""
        wav_path = None
        try:
            # Convert OGG to WAV for processing
            wav_path = await cls.convert_ogg_to_wav(file_path)
            
            # Get appropriate Vosk model for language
            vosk_model = await cls.get_vosk_model(language)
            
            # Process audio with Vosk
            wf = wave.open(wav_path, "rb")
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                print("Audio file must be WAV format mono PCM.")
                return None
                
            recognizer = KaldiRecognizer(vosk_model, wf.getframerate())
            recognizer.SetWords(True)
            
            results = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    part_result = json.loads(recognizer.Result())
                    results.append(part_result.get('text', ''))
            
            final_result = json.loads(recognizer.FinalResult())
            results.append(final_result.get('text', ''))
            
            text = ' '.join([r for r in results if r])
            return text if text else None

        except Exception as e:
            print(f"Vosk transcription error: {e}")
            return None
        finally:
            await cls.cleanup_files(file_path)
            if wav_path:
                await cls.cleanup_files(wav_path)

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
        
        # Transcribe voice using Vosk
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