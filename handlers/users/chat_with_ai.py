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
    """Voice processing helper class using Vosk with improved error handling"""
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
        """Convert OGG to WAV format with enhanced error handling"""
        wav_path = ogg_path.replace(".ogg", ".wav")
        
        try:
            # Ensure input file exists and has content
            if not os.path.exists(ogg_path) or os.path.getsize(ogg_path) == 0:
                raise Exception("Input file is missing or empty")

            # Use platform-specific ffmpeg command
            if IS_LINUX:
                cmd = [
                    "ffmpeg", "-y",  # Force overwrite
                    "-i", ogg_path,  # Input file
                    "-acodec", "pcm_s16le",  # Force correct audio codec
                    "-ac", "1",  # Mono audio
                    "-ar", "16000",  # 16kHz sample rate
                    "-f", "wav",  # WAV format
                    wav_path
                ]
            else:
                import imageio_ffmpeg
                ffmpeg_cmd = imageio_ffmpeg.get_ffmpeg_exe()
                cmd = [
                    ffmpeg_cmd, "-y",
                    "-i", ogg_path,
                    "-acodec", "pcm_s16le",
                    "-ac", "1",
                    "-ar", "16000",
                    "-f", "wav",
                    wav_path
                ]
            
            # Run ffmpeg with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
                if process.returncode != 0:
                    raise Exception(f"FFmpeg conversion failed: {stderr.decode()}")
            except asyncio.TimeoutError:
                process.kill()
                raise Exception("FFmpeg conversion timed out")

            # Verify output file
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:  # At least 1KB
                raise Exception("Converted file is missing or too small")

            return wav_path

        except Exception as e:
            print(f"Error converting audio: {str(e)}")
            if os.path.exists(wav_path):
                await VoiceProcessor.cleanup_files(wav_path)
            return None

    @classmethod
    async def transcribe_voice(cls, file_path: str, language: str) -> Optional[str]:
        """Transcribe voice to text with enhanced error handling"""
        wav_path = None
        try:
            # Convert to WAV
            wav_path = await cls.convert_ogg_to_wav(file_path)
            if not wav_path:
                raise Exception("Failed to convert audio file")

            # Get model for language
            try:
                vosk_model = await cls.get_vosk_model(language)
            except Exception as e:
                raise Exception(f"Failed to load voice recognition model: {str(e)}")

            # Open and verify WAV file
            with wave.open(wav_path, "rb") as wf:
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                    raise Exception("Invalid audio format")

                # Initialize recognizer
                recognizer = KaldiRecognizer(vosk_model, wf.getframerate())
                recognizer.SetWords(True)

                # Process audio in chunks
                text_parts = []
                chunk_size = 4000  # Smaller chunks for better memory management
                
                while True:
                    data = wf.readframes(chunk_size)
                    if not data:
                        break

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if result.get('text'):
                            text_parts.append(result['text'])

                # Get final result
                final_result = json.loads(recognizer.FinalResult())
                if final_result.get('text'):
                    text_parts.append(final_result['text'])

                # Combine results
                full_text = ' '.join(text_parts).strip()
                
                if not full_text:
                    raise Exception("No speech detected in audio")

                return full_text

        except Exception as e:
            print(f"Voice transcription error: {str(e)}")
            return None

        finally:
            # Clean up temporary files
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
    """Handle voice messages with comprehensive error handling"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    # Verify chat session
    if telegram_id not in user_sessions:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check rate limiting
    if await handle_rate_limit(telegram_id):
        await message.answer(
            text=messages[language]["time_waiter"],
            parse_mode=ParseMode.HTML
        )
        return
    
    # Show processing message
    thinking_msg = await message.answer(
        text=messages[language]["voice_processing"],
        parse_mode=ParseMode.HTML
    )
    
    voice_path = None
    try:
        # Verify voice message
        if not message.voice or not message.voice.file_id:
            raise Exception("Invalid voice message")

        # Download voice file
        voice = await bot.get_file(message.voice.file_id)
        voice_path = f"temp_voice_{message.message_id}_{telegram_id}.ogg"
        await bot.download_file(voice.file_path, voice_path)
        
        # Verify downloaded file
        if not os.path.exists(voice_path) or os.path.getsize(voice_path) < 100:
            raise Exception("Voice file download failed")
            
        # Transcribe voice
        voice_text = await VoiceProcessor.transcribe_voice(voice_path, language)
        
        if not voice_text:
            raise Exception("Could not recognize speech in audio")
        
        # Show transcribed text
        await message.answer(
            text=messages[language]["voice_recognized"].format(text=voice_text),
            parse_mode=ParseMode.HTML
        )
        
        # Process with AI
        await thinking_msg.delete()
        await process_message(message, voice_text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Voice processing error: {error_msg}")
        await thinking_msg.delete()
        await message.answer(
            text=messages[language]["voice_error"],
            parse_mode=ParseMode.HTML
        )
    finally:
        # Ensure cleanup
        if voice_path:
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

