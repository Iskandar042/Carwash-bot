"""
Shared helpers used by bot.py and all handlers.
Kept in a separate module to avoid circular imports.
"""
from telegram.ext import ContextTypes

_SESSION_KEY = "staff_role"


def _lang(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("lang", "ru")


def _is_staff(ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    return ctx.user_data.get(_SESSION_KEY) in ("worker", "admin")
