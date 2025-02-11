from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


inline_keyboard = [[
    InlineKeyboardButton(text="✅ Yes", callback_data='yes'),
    InlineKeyboardButton(text="❌ No", callback_data='no')
]]
are_you_sure_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)



# languages = [[
#     InlineKeyboardButton("🇺🇿 O'zbek", callback_data='uz'),
#     InlineKeyboardButton("🇷🇺 Русский", callback_data='ru'),
#     InlineKeyboardButton('🇺🇸 English', callback_data='eng')
# ]]

# languages_markup = InlineKeyboardMarkup(inline_keyboard=languages)
