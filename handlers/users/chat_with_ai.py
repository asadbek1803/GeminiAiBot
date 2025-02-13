import re
import asyncio
import google.generativeai as ai
from componets.messages import buttons, messages
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.enums.parse_mode import ParseMode
from loader import bot, db
from data.config import API_KEY
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton



ai.configure(api_key=API_KEY)
model = ai.GenerativeModel("gemini-pro")

router = Router()


def get_keyboard(language):
    """Foydalanuvchi tiliga mos Reply tugmalarni qaytaradi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[language]["btn_new_chat"]), KeyboardButton(text=buttons[language]["btn_stop"])],
            [KeyboardButton(text=buttons[language]["btn_continue"]), KeyboardButton(text=buttons[language]["btn_change_lang"])],
        ],
        resize_keyboard=True,  # Makes the keyboard smaller and neater
        one_time_keyboard=False  # Keyboard stays after clicking
    )


user_sessions = {}
user_last_request_time = {}

    

def format_text(text):
    """Matnni HTML formatiga o'tkazish"""
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)  # Bold
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)  # Italic
    text = re.sub(r"`([^`]*)`", r"<code>\1</code>", text)  # Inline code
    return text

@router.message(Command("chat"))
async def start_chat(message: types.Message):
    """Foydalanuvchi bilan AI chatbotni boshlash."""
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user.get("language", "uz") if user else "uz"

    if telegram_id not in user_sessions:
        user_sessions[telegram_id] = {
            "chat": model.start_chat(),
            "message_count": 0,
            "language": language
        }

    await message.answer(
        text="Chat boshlash uchun xabar yuboring!",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("stop"))
async def stop_chat(message: types.Message):
    """Foydalanuvchi chatni to'xtatadi."""
    telegram_id = message.from_user.id
    user = db.select_user(telegram_id=telegram_id)
    if telegram_id in user_sessions:
        del user_sessions[telegram_id]
        await message.answer(text = messages[user["language"]]["stop"], parse_mode=ParseMode.HTML)
    else:
        await message.answer(text= messages[user["language"]]["not_started"], parse_mode=ParseMode.HTML)

@router.message()
async def chat_with_ai(message: types.Message):
    """Foydalanuvchidan kelgan xabarga AI javob qaytaradi."""
    telegram_id = message.from_user.id
    user = db.select_user(telegram_id = telegram_id)
    # Foydalanuvchi uchun vaqtni tekshirish
    now = asyncio.get_event_loop().time()
    if telegram_id in user_last_request_time:
        elapsed_time = now - user_last_request_time[telegram_id]
        if elapsed_time < 1:  # Har bir foydalanuvchi uchun 1 soniyali limit
            await message.answer(text=messages[user["language"]]["time_waiter"])
            return

    user_last_request_time[telegram_id] = now

    if telegram_id not in user_sessions:
        await message.answer(text= messages[user["language"]]["not_started"], parse_mode=ParseMode.HTML)
        return

    session = user_sessions[telegram_id]
    language = session["language"]

    if session["message_count"] >= 20:
        del user_sessions[telegram_id]
        await message.answer(text=messages[user["language"]]["limit_reached"], parse_mode=ParseMode.HTML)
        return

    thinking_message = await message.answer(text = messages[user["language"]]["thinking"])

    try:
        response = session["chat"].send_message(message.text)
        session["message_count"] += 1  

        formatted_response = format_text(response.text)

        await asyncio.sleep(1)  # Har bir so‘rov orasida 1 soniya kutish
        await thinking_message.delete()

        await message.answer(
            text=formatted_response,
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await thinking_message.delete()
        await message.answer(f"Xatolik yuz berdi: {str(e)}", parse_mode=ParseMode.HTML)
