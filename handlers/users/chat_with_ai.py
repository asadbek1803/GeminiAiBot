import asyncio
import os
import json
import subprocess
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
    "uz": {"code": "uz", "vosk_model": "vosk-model-small-en"},  # Fallback to English if Uzbek model unavailable
    "tr": {"code": "tr", "vosk_model": "vosk-model-small-en"}   # Fallback to English if Turkish model unavailable
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
    async def convert_ogg_to_wav(ogg_path: str) -> Optional[str]:
        """Convert OGG to WAV format for Vosk processing with robust error handling"""
        wav_path = ogg_path.replace(".ogg", ".wav")
        
        try:
            # First attempt: Use direct ffmpeg command for better control
            if IS_LINUX:
                cmd = ["ffmpeg", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path, "-y"]
            else:
                import imageio_ffmpeg
                ffmpeg_cmd = imageio_ffmpeg.get_ffmpeg_exe()
                cmd = [ffmpeg_cmd, "-i", ogg_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path, "-y"]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                print(f"FFmpeg conversion failed: {result.stderr}")
                raise Exception("FFmpeg conversion produced empty file")
                
            return wav_path
            
        except Exception as e:
            print(f"Error converting audio: {str(e)}")
            return None

    @classmethod
    async def get_vosk_model(cls, language: str):
        """Get or load Vosk model for specified language with fallback"""
        model_path = SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES["eng"])["vosk_model"]
        
        # Always fallback to English if model doesn't exist
        if not os.path.exists(model_path):
            model_path = "vosk-model-small-en"
            if not os.path.exists(model_path):
                raise Exception(f"Vosk model not found: {model_path}")
        
        if model_path not in cls._models:
            try:
                cls._models[model_path] = Model(model_path)
            except Exception as e:
                print(f"Error loading Vosk model {model_path}: {e}")
                # Hard fallback to English if available
                fallback_model = "vosk-model-small-en"
                if fallback_model not in cls._models and os.path.exists(fallback_model):
                    cls._models[fallback_model] = Model(fallback_model)
                    return cls._models[fallback_model]
                raise
                
        return cls._models[model_path]

    @classmethod
    async def transcribe_voice(cls, file_path: str, language: str) -> Optional[str]:
        """Transcribe voice to text using Vosk with robust error handling"""
        wav_path = None
        try:
            # Convert OGG to WAV for processing
            wav_path = await cls.convert_ogg_to_wav(file_path)
            if not wav_path:
                return None
            
            # Check if WAV file exists and is valid
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
                print(f"Invalid WAV file: {wav_path}")
                return None
            
            # Get appropriate Vosk model for language
            try:
                vosk_model = await cls.get_vosk_model(language)
            except Exception as e:
                print(f"Could not load Vosk model: {e}")
                return None
            
            # Process audio with Vosk
            try:
                wf = wave.open(wav_path, "rb")
                
                # Verify WAV format
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                    print(f"Audio file must be WAV format mono PCM. Converting...")
                    # Try to re-convert with more specific parameters
                    os.remove(wav_path)
                    if IS_LINUX:
                        cmd = ["ffmpeg", "-i", file_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", wav_path, "-y"]
                    else:
                        import imageio_ffmpeg
                        ffmpeg_cmd = imageio_ffmpeg.get_ffmpeg_exe()
                        cmd = [ffmpeg_cmd, "-i", file_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", wav_path, "-y"]
                    
                    subprocess.run(cmd, capture_output=True, check=True)
                    wf = wave.open(wav_path, "rb")
                
                recognizer = KaldiRecognizer(vosk_model, wf.getframerate())
                recognizer.SetWords(True)
                
                results = []
                data_chunk = wf.readframes(4000)
                while len(data_chunk) > 0:
                    if recognizer.AcceptWaveform(data_chunk):
                        part_result = json.loads(recognizer.Result())
                        results.append(part_result.get('text', ''))
                    data_chunk = wf.readframes(4000)
                
                final_result = json.loads(recognizer.FinalResult())
                results.append(final_result.get('text', ''))
                
                text = ' '.join([r for r in results if r])
                return text if text else None
                
            except Exception as e:
                print(f"Error during Vosk processing: {e}")
                return None

        except Exception as e:
            print(f"Vosk transcription error: {e}")
            return None
        finally:
            await cls.cleanup_files(file_path)
            if wav_path:
                await cls.cleanup_files(wav_path)

@router.message(Command("chat"))
@router.message(lambda message: message.text and any(message.text == buttons[lang]["btn_new_chat"] for lang in ["uz", "ru", "eng"]))
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
@router.message(lambda message: message.text and any(message.text == buttons[lang]["btn_stop"] for lang in ["uz", "ru", "eng"]))
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
    """Handle voice messages with improved error handling"""
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
        
        if not os.path.exists(voice_path) or os.path.getsize(voice_path) < 100:
            raise Exception("Voice file download failed or file is too small")
            
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
        if voice_path and os.path.exists(voice_path):
            await VoiceProcessor.cleanup_files(voice_path)

async def handle_rate_limit(telegram_id: int) -> bool:
    """Handle request rate limiting"""
    now = asyncio.get_event_loop().time()
    if telegram_id in user_last_request_time:
        if (now - user_last_request_time[telegram_id]) < 1.5:
            return True
    user_last_request_time[telegram_id] = now
    return False

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

@router.message(lambda message: message.text and any(message.text == buttons[lang]["btn_continue"] for lang in ["uz", "ru", "eng"]))
async def continue_chat(message: types.Message):
    """Continue the existing chat session."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    if telegram_id not in user_sessions:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
    else:
        await message.answer(
            text=messages[language]["continue"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )

