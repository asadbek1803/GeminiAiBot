import re
import asyncio
import google.generativeai as ai
from componets.messages import buttons, messages
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums.parse_mode import ParseMode
from loader import bot, db
from data.config import API_KEY
import speech_recognition as sr
import os
from pydub import AudioSegment
import ffmpeg

ai.configure(api_key=API_KEY)
model = ai.GenerativeModel("gemini-pro")

router = Router()

user_sessions = {}
user_last_request_time = {}

def get_keyboard(language):
    """Foydalanuvchi tiliga mos Reply tugmalarni qaytaradi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[language]["btn_new_chat"]), KeyboardButton(text=buttons[language]["btn_stop"])],
            [KeyboardButton(text=buttons[language]["btn_continue"]), KeyboardButton(text=buttons[language]["btn_change_lang"])],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )



def format_text(text):
    """Matnni HTML formatiga o'tkazish"""
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]*)`", r"<code>\1</code>", text)
    return text

@router.message(Command("chat"))
@router.message(lambda message: message.text == buttons["uz"]["btn_new_chat"] or
                                message.text == buttons["ru"]["btn_new_chat"] or
                                message.text == buttons["eng"]["btn_new_chat"])
async def start_chat(message: types.Message):
    """Foydalanuvchi bilan AI chatbotni boshlash."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"

    if telegram_id not in user_sessions:
        user_sessions[telegram_id] = {
            "chat": model.start_chat(),
            "message_count": 0,
            "language": language
        }

    await message.answer(text=messages[language]["start"], parse_mode=ParseMode.HTML)

@router.message(Command("stop"))
async def stop_chat(message: types.Message):
    """Foydalanuvchi chatni to'xtatadi."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"

    if telegram_id in user_sessions:
        del user_sessions[telegram_id]
        await message.answer(text=messages[language]["stop"], parse_mode=ParseMode.HTML)
    else:
        await message.answer(text=messages[language]["not_started"], parse_mode=ParseMode.HTML)
async def convert_voice_to_text(voice_file_path: str, language: str = "uz-UZ") -> str:
    """Ovozli xabarni matnga o'girish"""
    try:
        # Convert .oga to .wav format using ffmpeg
        wav_path = voice_file_path.replace(".oga", ".wav")
        
        # Run ffmpeg conversion
        stream = ffmpeg.input(voice_file_path)
        stream = ffmpeg.output(stream, wav_path)
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

        # Initialize recognizer
        recognizer = sr.Recognizer()
        
        # Read the audio file
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            
            # Convert speech to text
            text = recognizer.recognize_google(audio_data, language=language)
            
        # Clean up temporary files
        os.remove(voice_file_path)
        os.remove(wav_path)
        
        return text
    
    except Exception as e:
        print(f"FFmpeg error: {e}")
        return ""
    except Exception as e:
        print(f"Error in speech recognition: {str(e)}")
        return ""

@router.message(F.voice)
async def handle_voice(message: types.Message):
    """Ovozli xabarlarni qayta ishlash"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    if telegram_id not in user_sessions:
        await message.answer(text=messages[language]["not_started"], parse_mode=ParseMode.HTML)
        return

    thinking_message = await message.answer(text=messages[language]["voice_processing"], parse_mode=ParseMode.HTML)

    voice_path = None
    wav_path = None

    try:
        # Download voice message
        voice = await bot.get_file(message.voice.file_id)
        voice_path = f"temp_{message.message_id}.oga"
        await bot.download_file(voice.file_path, voice_path)
        
        # Convert voice to text
        lang_code = {"uz": "uz-UZ", "ru": "ru-RU", "eng": "en-US"}[language]
        voice_text = await convert_voice_to_text(voice_path, lang_code)

        if not voice_text:
            await thinking_message.delete()
            await message.answer(text=messages[language]["voice_error"], parse_mode=ParseMode.HTML)
            return

        # Show recognized text to user
        await message.answer(
            text=messages[language]["voice_recognized"].format(text=voice_text),
            parse_mode=ParseMode.HTML
        )

        # Process the converted text with AI
        await thinking_message.delete()
        await process_message(message, voice_text)

    except Exception as e:
        await thinking_message.delete()
        await message.answer(f"Xatolik yuz berdi: {str(e)}", parse_mode=ParseMode.HTML)
    
    finally:
        # Clean up any remaining temporary files
        try:
            if voice_path and os.path.exists(voice_path):
                os.remove(voice_path)
            wav_path = voice_path.replace(".oga", ".wav")
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception as e:
            print(f"Error cleaning up files: {str(e)}")

async def process_message(message: types.Message, text: str = None):
    """Xabarni qayta ishlash (matn yoki ovozdan o'girilgan)"""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user["language"] if user else "uz"
    
    now = asyncio.get_event_loop().time()
    if telegram_id in user_last_request_time:
        elapsed_time = now - user_last_request_time[telegram_id]
        if elapsed_time < 1:
            await message.answer(text=messages[language]["time_waiter"], parse_mode=ParseMode.HTML)
            return

    user_last_request_time[telegram_id] = now
    session = user_sessions[telegram_id]

    if session["message_count"] >= 20:
        del user_sessions[telegram_id]
        await message.answer(text=messages[language]["limit_reached"], parse_mode=ParseMode.HTML)
        return

    thinking_message = await message.answer(text=messages[language]["thinking"], parse_mode=ParseMode.HTML)

    try:
        input_text = text if text else message.text
        response = session["chat"].send_message(input_text)
        session["message_count"] += 1

        formatted_response = format_text(response.text)

        await asyncio.sleep(1)
        await thinking_message.delete()

        await message.answer(
            text=formatted_response,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await thinking_message.delete()
        await message.answer(f"Xatolik yuz berdi: {str(e)}", parse_mode=ParseMode.HTML)

@router.message()
async def chat_with_ai(message: types.Message):
    """Foydalanuvchidan kelgan matnli xabarga AI javob qaytaradi."""
    await process_message(message)