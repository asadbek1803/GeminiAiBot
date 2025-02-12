from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.enums.parse_mode import ParseMode
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from aiogram.types.web_app_info import WebAppInfo
from aiogram.fsm.context import FSMContext
from data.config import ADMINS
from componets.messages import messages, buttons
from datetime import datetime

router = Router()


# Tilni tanlash uchun inline tugmalar
languages_markup = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data='uz')],
    [InlineKeyboardButton(text="🇷🇺 Русский", callback_data='ru')],
    [InlineKeyboardButton(text='🇺🇸 English', callback_data='eng')]
])



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


@router.message(CommandStart())
async def do_start(message: types.Message):
    """Foydalanuvchini tekshirish va u tanlagan til bo'yicha xabar yuborish."""
    
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name

    # Foydalanuvchi allaqachon ro'yxatdan o'tganligini tekshirish
    user = await db.select_user(telegram_id=telegram_id)

    if user:
        language = user.get("language", "uz")  # Agar til mavjud bo'lmasa, default "uz"
        text = messages[language]["start"].format(name=full_name)
        await message.answer(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(language)
        )
    else:
        text = f"Assalomu alaykum, <b>{full_name}</b>! 👋\n{messages['uz']['choose_lang']}"
        await message.answer(
            text=text,
            reply_markup=languages_markup,
            parse_mode=ParseMode.HTML
        )



@router.callback_query(lambda callback_data: callback_data.data in ["uz", "ru", "eng"])
async def create_account(callback_data: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchini bazaga qo'shish va unga til tanlanganiga qarab xabar yuborish."""
    
    await callback_data.message.edit_reply_markup()
    
    telegram_id = callback_data.from_user.id
    full_name = callback_data.from_user.full_name
    username = callback_data.from_user.username
    language = callback_data.data

    welcome_messages = {
        "uz": ("Akkaunt muvaffaqiyatli yaratildi ✅", 
               f"Assalomu alaykum <b>{full_name}</b>! Bizning Gemini AI botga xush kelibsiz 😊"),
        "ru": ("Аккаунт успешно создан ✅", 
               f"Привет <b>{full_name}</b>! Добро пожаловать в наш AI-бот Gemini 😊"),
        "eng": ("Account created successfully ✅", 
                f"Hello <b>{full_name}</b>! Welcome to our Gemini AI bot 😊")
    }

    try:
        user = await db.add_user(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            language=language
        )
        now = datetime.now()
        success_msg, welcome_msg = welcome_messages[language]

        await callback_data.answer(text=success_msg)
        await bot.send_message(
            chat_id=telegram_id, 
            text=welcome_msg, 
            parse_mode=ParseMode.HTML
        )
        

        # Adminlarga xabar yuborish
        admin_msg = (
            f"Yangi foydalanuvchi ro'yxatdan o'tdi ✅\n"
            f"👤 Ism: <b>{full_name}</b>\n"
            f"📌 Telegram ID: <code>{telegram_id}</code>\n"
            f"🌍 Til: <b>{language.upper()}</b>\n"
            f"📅 Qo'shilgan sana: <b> {now} </b>"
        )
        
        for admin in ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin, 
                    text=admin_msg, 
                    parse_mode=ParseMode.HTML
                )
            except Exception as error:
                logger.info(f"Xatolik: Admin {admin} ga xabar jo'natilmadi. {error}")

    except Exception as e:
        await callback_data.answer(
            text=f"Xatolik yuz berdi ❌\n{str(e)}"
        )


@router.message(Command("change_language"))
@router.callback_query(lambda callback_data: callback_data.data == "change_language")
async def change_language(callback_data: types.CallbackQuery):
    """Foydalanuvchiga tilni tanlash menyusini ko‘rsatish."""
    
    
    
    language_buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="update_uz")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="update_ru")],
            [InlineKeyboardButton(text="🇺🇸 English", callback_data="update_eng")]
        ]
    )

    msg = await bot.send_message(
        chat_id = callback_data.from_user.id,
        text="🌍 Iltimos, yangi tilni tanlang:\n\n🇺🇿 O‘zbekcha | 🇷🇺 Русский | 🇺🇸 English",
        reply_markup=language_buttons
    )

    

@router.callback_query(lambda callback_data: callback_data.data in ["update_uz", "update_ru", "update_eng"])
async def update_language(callback_data: types.CallbackQuery):
    """Foydalanuvchining tilini bazada yangilash."""
    
    await callback_data.message.edit_reply_markup()
    
    telegram_id = callback_data.from_user.id
    new_language = callback_data.data.split("update_")[1]  # To'g'ri formatlash

    try:
        await db.update_user_language(telegram_id, new_language)
    except Exception as e:
        print(f"Tilni yangilashda xatolik: {e}")

    confirmation_messages = {
        "uz": "✅ Til muvaffaqiyatli o‘zgartirildi. Endi sizning interfeysingiz o‘zbek tilida bo‘ladi.",
        "ru": "✅ Язык успешно изменен. Теперь ваш интерфейс будет на русском языке.",
        "eng": "✅ Language successfully changed. Now your interface will be in English."
    }

    await callback_data.message.answer(
        text=confirmation_messages[new_language]
    )
