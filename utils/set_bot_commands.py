from aiogram import Bot
from aiogram.methods.set_my_commands import BotCommand
from aiogram.types import BotCommandScopeAllPrivateChats


async def set_default_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="🔄️ Botni ishga tushirish"),
        BotCommand(command="/help", description="📑 Yordam"),
        BotCommand(command="/change_language", description="🌐 Tilni o'zgartirish"),
        BotCommand(command="/new_chat", description="🤖 Yangi chat"),
        BotCommand(command="/stop_chat", description="❌ Chatni to'xtatish")
    ]
    await bot.set_my_commands(commands=commands, scope=BotCommandScopeAllPrivateChats())
