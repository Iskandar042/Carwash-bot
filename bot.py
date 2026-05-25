"""
Leadgram Car Wash — Telegram Bot
Entry point. Run with: python bot.py
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from keyboards import main_menu, staff_menu
from handlers.customer import build_handler as customer_handler
from handlers.staff import build_handlers as staff_handlers, staff_logout, view_queue

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "друг"
    await update.message.reply_text(
        f"👋 Привет, {name}!\n\n"
        "🚗 <b>Leadgram — Автомойка</b>\n\n"
        "Что вы хотите сделать?",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 <b>Как пользоваться ботом</b>\n\n"
        "<b>Для клиентов:</b>\n"
        "• Нажмите «🚗 Проверить статус авто» и введите гос. номер.\n\n"
        "<b>Для сотрудников:</b>\n"
        "• Нажмите «👷 Вход для персонала» и введите пароль.\n"
        "• После входа доступны: приём авто, обновление статуса и оплаты.\n\n"
        "Команды:\n"
        "/start — главное меню\n"
        "/cancel — отменить текущее действие",
        parse_mode="HTML",
    )


async def queue_shortcut(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow staff to view queue via text button without a ConversationHandler."""
    await view_queue(update, ctx)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set — check your .env file")

    app = Application.builder().token(BOT_TOKEN).build()

    # Core commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))

    # Staff logout + queue view (simple message handlers, no state)
    app.add_handler(MessageHandler(filters.Regex("^🚪 Выйти$"), staff_logout))
    app.add_handler(MessageHandler(filters.Regex("^📋 Текущая очередь$"), queue_shortcut))

    # Conversation handlers (order matters — more specific first)
    for handler in staff_handlers():
        app.add_handler(handler)
    app.add_handler(customer_handler())

    logger.info("Bot starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
