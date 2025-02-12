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



ai.configure(api_key=API_KEY)
model = ai.GenerativeModel("gemini-pro")

router = Router()


def get_keyboard(language):
    """Foydalanuvchi tiliga mos Inline tugmalarni qaytaradi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=buttons[language]["btn_new_chat"], callback_data="new_chat")],
            [InlineKeyboardButton(text=buttons[language]["btn_stop"], callback_data="stop_chat")],
            [InlineKeyboardButton(text=buttons[language]["btn_continue"], callback_data="continue_chat")],
            [InlineKeyboardButton(text=buttons[language]["btn_change_lang"], callback_data="change_language")]
        ]
    )



# Har bir foydalanuvchi uchun chat sessiyasini saqlash
user_sessions = {}

# Foydalanuvchi tiliga mos xabarlarni sozlash


def format_text(text):
    """Matnni HTML formatiga o'tkazish (bold, italic, underline, strikethrough, code)"""
    
    # Kod bloklarini formatlash
    text = re.sub(r"```([a-zA-Z]*)\n(.*?)```", r"<pre><code class='\1'>\2</code></pre>", text, flags=re.DOTALL)
    
    # Inline code
    text = re.sub(r"`([^`]*)`", r"<code>\1</code>", text)
    
    # Bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    
    # Italic
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    
    # Underline
    text = re.sub(r"__([^_]+)__", r"<u>\1</u>", text)
    
    # Strikethrough
    text = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", text)
    
    return text


@router.message(Command("chat"))
@router.callback_query(lambda c: c.data == "new_chat")
async def start_chat(message: types.Message):
    """Foydalanuvchi bilan AI chatbot orqali suhbatni boshlash."""
    
    telegram_id = message.from_user.id

    # Foydalanuvchining tilini bazadan olish
    user = await db.select_user(telegram_id=telegram_id)
    language = user.get("language", "uz") if user else "uz"

    # Agar foydalanuvchi uchun sessiya mavjud bo'lmasa, yangisini yaratamiz
    if telegram_id not in user_sessions:
        user_sessions[telegram_id] = {
            "chat": model.start_chat(),
            "message_count": 0,
            "language": language
        }

    await message.answer(
        text=messages[language]["start"],
        parse_mode=ParseMode.HTML
    )

@router.message(Command("stop"))
@router.callback_query(lambda c: c.data == "stop_chat")
async def stop_chat(message: types.Message):
    """Foydalanuvchi bilan suhbatni to'xtatish."""
    
    telegram_id = message.from_user.id
    user = await db.select_user(telegram_id=telegram_id)
    language = user.get("language", "uz") if user else "uz"

    if telegram_id in user_sessions:
        del user_sessions[telegram_id]
        await message.answer(
            text=messages[language]["stop"],
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML
        )

@router.message()
async def chat_with_ai(message: types.Message):
    """AI chatbotga foydalanuvchi xabarini yuborish va javob olish."""
    
    telegram_id = message.from_user.id
    
    if telegram_id not in user_sessions:
        user = await db.select_user(telegram_id=telegram_id)
        language = user.get("language", "uz") if user else "uz"
        msg = await message.answer(
            text=messages[language]["not_started"],
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
        return

    session = user_sessions[telegram_id]
    language = session["language"]
    
    
    if session["message_count"] >= 20:
        del user_sessions[telegram_id]
        await message.answer(
            text=messages[language]["limit_reached"],
            parse_mode=ParseMode.HTML
        )
        return

    await msg.delete()
    thinking_message = await message.answer(
        text=messages[language]["thinking"],
        parse_mode=ParseMode.HTML
    )

    try:
        response = session["chat"].send_message(message.text)
        session["message_count"] += 1  

        # Matnni to'liq formatlash (kod va markdown)
        formatted_response = format_text(response.text)

        await thinking_message.delete()

        await message.answer(
            text=messages[language]["bot_response"].format(formatted_response),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await thinking_message.delete()
        
        await message.answer(
            text=messages[language]["error"].format(str(e)),
            parse_mode=ParseMode.HTML
        )