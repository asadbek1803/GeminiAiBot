import logging
import asyncio
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from loader import db, bot
from keyboards.inline.buttons import are_you_sure_markup
from states.test import AdminState
from filters.admin import IsBotAdminFilter
from data.config import ADMINS
from keyboards.inline.admin_menu import admin_menu_markup
from utils.pgtoexcel import export_to_excel

router = Router()


@router.message(Command('admin'), IsBotAdminFilter(ADMINS))
async def welcome_to_admin(message: types.Message):
    await message.answer(text = f"Assalomu alaykum Admin 😊\n Admin Panel bilan tanishing 👇👇👇", reply_markup=admin_menu_markup)


@router.message(Command('allusers'), IsBotAdminFilter(ADMINS))
@router.callback_query(lambda c: c.data == "allusers", IsBotAdminFilter(ADMINS))
async def all_users(event: types.Message | types.CallbackQuery):
    users = await db.select_all_users()
    file_path = "data/users_list.xlsx"

    await event.answer("Tayyorlanmoqda ⌛")

    await export_to_excel(users, ['ID', 'Full Name', 'Username', 'Telegram ID', "Created at", "Language"], file_path)

    await (event.message if isinstance(event, types.CallbackQuery) else event).answer_document(types.input_file.FSInputFile(file_path))


@router.message(Command('reklama'), IsBotAdminFilter(ADMINS))
async def ask_ad_content(message: types.Message, state: FSMContext):
    await message.answer("Reklama uchun post yuboring")
    await state.set_state(AdminState.ask_ad_content)


@router.message(AdminState.ask_ad_content, IsBotAdminFilter(ADMINS))
async def send_ad_to_users(message: types.Message, state: FSMContext):
    users = await db.select_all_users()
    count = 0
    for user in users:
        user_id = user[3]
        # print(user_id)
        try:
            await message.send_copy(chat_id=user_id)
            count += 1
            await asyncio.sleep(0.05)
        except Exception as error:
            logging.info(f"Ad did not send to user: {user_id}. Error: {error}")
    await message.answer(text=f"Reklama {count} ta foydalauvchiga muvaffaqiyatli yuborildi.")
    await state.clear()


@router.message(Command('cleandb'), IsBotAdminFilter(ADMINS))
async def ask_are_you_sure(message: types.Message, state: FSMContext):
    msg = await message.reply("Haqiqatdan ham bazani tozalab yubormoqchimisiz?", reply_markup=are_you_sure_markup)
    await state.update_data(msg_id=msg.message_id)
    await state.set_state(AdminState.are_you_sure)


@router.callback_query(AdminState.are_you_sure, IsBotAdminFilter(ADMINS))
async def clean_db(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    if call.data == 'yes':
        await db.delete_users()
        text = "Baza tozalandi!"
    elif call.data == 'no':
        text = "Bekor qilindi."
    await bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=msg_id)
    await state.clear()
