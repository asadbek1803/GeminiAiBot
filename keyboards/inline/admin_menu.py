from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton



# inline_keyboard = [[
#     InlineKeyboardButton(text="✅ Yes", callback_data='yes'),
#     InlineKeyboardButton(text="❌ No", callback_data='no')
# ]]
# are_you_sure_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

admins_menu = [
    [InlineKeyboardButton(text="📤 Reklama yuborish", callback_data="reklama"), InlineKeyboardButton(text="📊 Statistika", callback_data="statistics")],
    [InlineKeyboardButton(text = "📃 Ma'lumotlar bazasini yuklab olish (Excel)", callback_data="allusers")],
    [InlineKeyboardButton(text="🗑️ Bazani tozalash", callback_data="cleandb")]
]

admin_menu_markup = InlineKeyboardMarkup(inline_keyboard=admins_menu)