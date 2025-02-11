from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
router = Router()


@router.message(Command('help'))
async def bot_help(message: types.Message):
    channel = [
        [InlineKeyboardButton(text="Daha IT Company", url="https://t.me/DahaITCompany")]
    ]
    channel_markup = InlineKeyboardMarkup(inline_keyboard=channel)
    text = ("Bot haqida: ",
            "Bot Daha IT Companiyasi tomonidan yozilgan. DeepSeek AI",
            "Bot kommandalari: ",
            "/start - 🔄️ Botni ishga tushirish",
            "/change_language - 🌐 Tilni o'zgartirish",
            "/new_chat - 🤖 Yangi chat", 
            "/stop_chat - ❌ Chatni to'xtatish",
            "Bizning ijtimoiy tarmoqlarga obuna bo'lishni unutmang ;) "
            )
    await message.answer(text="\n".join(text), reply_markup=channel_markup)
