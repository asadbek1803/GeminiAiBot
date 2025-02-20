import asyncio
import os
import json
from typing import Optional
import assemblyai as aai
from collections import defaultdict
from datetime import datetime, timedelta
import re
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums.parse_mode import ParseMode
from loader import bot, db
from data.config import API_KEY, ASSEMBLYAI_API_KEY
from componets.messages import buttons, messages
import google.generativeai as ai

# Configure AI models
aai.settings.api_key = ASSEMBLYAI_API_KEY
ai.configure(api_key=API_KEY)
model = ai.GenerativeModel("gemini-pro")

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
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text

async def safe_delete_message(message: types.Message):
    """Safely delete a message, catching any deletion errors"""
    try:
        await message.delete()
    except Exception as e:
        print(f"Error deleting message: {e}")
        pass

# Rate limiting configuration
class VoiceRateLimiter:
    def __init__(self):
        self.active_users = defaultdict(int)
        self.last_cleanup = datetime.now()
        self.cleanup_interval = timedelta(minutes=5)
        self.max_concurrent_users = 3
        self.cooldown_period = timedelta(minutes=2)
        self.user_cooldowns = {}

    def cleanup_old_entries(self):
        """Remove old entries from tracking"""
        if datetime.now() - self.last_cleanup > self.cleanup_interval:
            current_time = datetime.now()
            self.user_cooldowns = {
                user: time for user, time in self.user_cooldowns.items()
                if current_time - time < self.cooldown_period
            }
            self.last_cleanup = current_time

    async def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[timedelta]]:
        """Check if user should be rate limited"""
        self.cleanup_old_entries()
        current_time = datetime.now()

        if user_id in self.user_cooldowns:
            wait_time = self.cooldown_period - (current_time - self.user_cooldowns[user_id])
            if wait_time > timedelta(0):
                return True, wait_time
            else:
                del self.user_cooldowns[user_id]

        if len(self.active_users) >= self.max_concurrent_users:
            self.user_cooldowns[user_id] = current_time
            return True, self.cooldown_period

        self.active_users[user_id] = current_time
        return False, None

    def release_user(self, user_id: int):
        """Release user from active processing"""
        if user_id in self.active_users:
            del self.active_users[user_id]

rate_limiter = VoiceRateLimiter()

class VoiceProcessor:
    """Voice processing helper class using AssemblyAI"""

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
        """Transcribe voice to text using AssemblyAI"""
        try:
            transcriber = aai.Transcriber()
            
            config = {}
            if language in ["en", "eng"]:
                config["language_code"] = "en"
            elif language == "ru":
                config["language_code"] = "ru"
            
            transcript = transcriber.transcribe(
                file_path,
                **config
            )

            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"Transcription failed: {transcript.error}")

            return transcript.text

        except Exception as e:
            print(f"Voice transcription error: {str(e)}")
            return None

        finally:
            await VoiceProcessor.cleanup_files(file_path)

# Message Handlers
@router.message(Command("chat"))
@router.message(lambda message: message.text and any(message.text == buttons[lang]["btn_new_chat"] for lang in ["uz", "ru", "eng"]))
async def start_chat(message: types.Message):
    """Start AI chatbot with user."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"

    # Reset session if exists
    if telegram_id in user_sessions:
        del user_sessions[telegram_id]

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
    
    is_limited, wait_time = await rate_limiter.check_rate_limit(telegram_id)
    if is_limited:
        wait_minutes = round(wait_time.total_seconds() / 60, 1)
        await message.answer(
            text=messages[language]["time_waiter"].format(minutes=wait_minutes),
            parse_mode=ParseMode.HTML
        )
        return
    
    thinking_msg = await message.answer(
        text=messages[language]["voice_processing"],
        parse_mode=ParseMode.HTML
    )
    
    voice_path = None
    try:
        if not message.voice or not message.voice.file_id:
            raise Exception("Invalid voice message")

        voice = await bot.get_file(message.voice.file_id)
        voice_path = f"temp_voice_{message.message_id}_{telegram_id}.ogg"
        await bot.download_file(voice.file_path, voice_path)
        
        if not os.path.exists(voice_path) or os.path.getsize(voice_path) < 100:
            raise Exception("Voice file download failed")
            
        voice_text = await VoiceProcessor.transcribe_voice(voice_path, language)
        
        if not voice_text:
            raise Exception("Could not recognize speech in audio")
        
        await safe_delete_message(thinking_msg)
        await message.answer(
            text=messages[language]["voice_recognized"].format(text=voice_text),
            parse_mode=ParseMode.HTML
        )
        
        await process_message(message, voice_text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Voice processing error: {error_msg}")
        await safe_delete_message(thinking_msg)
        await message.answer(
            text=f"{messages[language]['voice_error']}\n{error_msg}",
            parse_mode=ParseMode.HTML
        )
    finally:
        rate_limiter.release_user(telegram_id)
        if voice_path:
            await VoiceProcessor.cleanup_files(voice_path)

@router.message(F.text)
async def handle_text(message: types.Message):
    """Handle text messages"""
    telegram_id = message.from_user.id
    
    # Skip processing for command buttons
    if any(message.text == buttons[lang][btn] for lang in ["uz", "ru", "eng"] 
           for btn in ["btn_new_chat", "btn_stop", "btn_continue", "btn_change_lang"]):
        return
    
    await process_message(message)

async def process_message(message: types.Message, text: Optional[str] = None):
    """Process messages (both voice and text)"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    session = user_sessions.get(telegram_id)
    if not session:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
        return
    
    # Check message limit
    if session["message_count"] >= 20:
        del user_sessions[telegram_id]
        await message.answer(
            text=messages[language]["limit_reached"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
        return
    
    # Check rate limiting for text messages
    current_time = datetime.now()
    last_request_time = user_last_request_time.get(telegram_id)
    if last_request_time and (current_time - last_request_time).total_seconds() < 1:
        await message.answer(
            text=messages[language]["too_fast"],
            parse_mode=ParseMode.HTML
        )
        return
    
    user_last_request_time[telegram_id] = current_time
    
    thinking_msg = await message.answer(
        text=messages[language]["thinking"],
        parse_mode=ParseMode.HTML
    )
    
    try:
        input_text = text if text else message.text
        response = session["chat"].send_message(input_text)
        session["message_count"] += 1
        
        formatted_response = format_text(response.text)
        
        await safe_delete_message(thinking_msg)
        await message.answer(
            text=formatted_response,
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
    except Exception as e:
        print(f"Error processing message: {e}")
        await safe_delete_message(thinking_msg)
        await message.answer(
            text=messages[language]["error"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
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