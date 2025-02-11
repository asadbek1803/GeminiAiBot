from aiogram import Router
from aiogram.enums import ChatType

from filters import ChatTypeFilter


def setup_routers() -> Router:
    from .users import admin, start, help, chat_with_ai
    from .errors import error_handler

    router = Router()

    # Agar kerak bo'lsa, o'z filteringizni o'rnating
    start.router.message.filter(ChatTypeFilter(chat_types=[ChatType.PRIVATE]))

    router.include_routers(admin.router, start.router, help.router, chat_with_ai.router, error_handler.router)

    return router
