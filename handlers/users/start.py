from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.enums.parse_mode import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from aiogram.fsm.context import FSMContext
from data.config import ADMINS
from componets.messages import messages, buttons
from datetime import datetime

router = Router()

# Tilni tanlash uchun ReplyKeyboardMarkup
def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿 O'zbek"), KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text='🇺🇸 English'), KeyboardButton(text="🇹🇷 Türkçe")]
        ],
        resize_keyboard=True
    )

def get_keyboard(language):
    """Foydalanuvchi tiliga mos Reply tugmalarni qaytaradi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[language]["btn_new_chat"]), KeyboardButton(text=buttons[language]["btn_stop"])],
            [KeyboardButton(text=buttons[language]["btn_continue"]), KeyboardButton(text=buttons[language]["btn_change_lang"])]
        ],
        resize_keyboard=True
    )

@router.message(CommandStart())
async def do_start(message: types.Message):
    """Foydalanuvchini tekshirish va u tanlagan til bo'yicha xabar yuborish."""
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    user = await db.select_user(telegram_id=telegram_id)

    if user:
        language = user.get("language", "uz")
        text = messages[language]["start_command"].format(name=full_name)
        await message.answer(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
    else:
        text = f"Assalomu alaykum, <b>{full_name}</b>! 👋\n{messages['uz']['choose_lang']}"
        await message.answer(
            text=text,
            reply_markup=language_keyboard(),
            parse_mode=ParseMode.HTML
        )

@router.message(Command("change_language"))
@router.message(lambda message: message.text == buttons["uz"]["btn_change_lang"] or
                                message.text == buttons["ru"]["btn_change_lang"] or
                                message.text == buttons["eng"]["btn_change_lang"] or
                                message.text == buttons["tr"]["btn_change_lang"]
                                )
async def get_lang_keyboards(message: types.Message):
    msg = await bot.send_message(
        chat_id=message.from_user.id,
        text="🌍 Iltimos, yangi tilni tanlang:\n\n🇺🇿 O‘zbekcha | 🇷🇺 Русский | 🇺🇸 English |  🇹🇷 Türkçe",
        reply_markup=language_keyboard()
    )

@router.message(lambda message: message.text in ["🇺🇿 O'zbek", "🇷🇺 Русский", "🇺🇸 English", "🇹🇷 Türkçe"])
async def create_or_update_account(message: types.Message):
    """Foydalanuvchini bazaga qo'shish yoki tilini yangilash."""
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    language_map = {"🇺🇿 O'zbek": "uz", "🇷🇺 Русский": "ru", "🇺🇸 English": "eng", "🇹🇷 Türkçe": "tr"}
    language = language_map[message.text]

    welcome_messages = {
        "uz": ("Akkaunt muvaffaqiyatli yaratildi ✅", 
               f"Assalomu alaykum <b>{full_name}</b>! Bizning Gemini AI botga xush kelibsiz 😊"),
        "ru": ("Аккаунт успешно создан ✅", 
               f"Привет <b>{full_name}</b>! Добро пожаловать в наш AI-бот Gemini 😊"),
        "eng": ("Account created successfully ✅", 
                f"Hello <b>{full_name}</b>! Welcome to our Gemini AI bot 😊"),
        "tr": ("Hesap başarıyla oluşturuldu ✅",
               f"Merhaba <b>{full_name}</b>! Gemini AI botumuza hoş geldiniz 😊")
    }

    update_messages = {
        "uz": "Til muvaffiqiyatli yangilandi ✅",
        "ru": "Язык успешно обновлен ✅",
        "eng": "The language has been updated successfully ✅",
        "tr": "Dil başarıyla güncellendi ✅"
    }
    try:
        user = await db.select_user(telegram_id=telegram_id)
        if user:
            await db.update_user_language(telegram_id, language)
            await message.answer(text=update_messages[language], reply_markup=get_keyboard(language))
        else:
            await db.add_user(
                telegram_id=telegram_id,
                full_name=full_name,
                username=username,
                language=language
            )
            success_msg, welcome_msg = welcome_messages[language]
            await message.answer(text=success_msg)
            await message.answer(
                text=welcome_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=get_keyboard(language=language)
            )
            for admin in ADMINS:
                try:
                    admin_message = f"🆕 Yangi foydalanuvchi qo'shildi:\n👤 Ism: {full_name}\n🔹 Username: @{username}\n🆔 Telegram ID: {telegram_id}\n📅 Qo'shilgan vaqt: {created_at}"
                    await bot.send_message(chat_id=admin, text=admin_message, parse_mode=ParseMode.HTML)
                except Exception as e:
                    logger.error(f"Adminga xabar yuborishda xatolik: {e}")
    except Exception as e:
        await message.answer(text=f"Xatolik yuz berdi ❌\n{str(e)}")
