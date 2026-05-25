"""
Leadgram Car Wash — Telegram Bot
Run: python bot.py
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from lang import t
from keyboards import main_menu, staff_menu, lang_keyboard
from handlers.customer import build_handler as customer_handler
from handlers.staff import (
    build_handlers as staff_handlers,
    staff_logout, view_queue,
    _is_staff,
)

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Language helpers ──────────────────────────────────────────────────────────

def _lang(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("lang", "ru")


# ── /start — show language picker ─────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        t("select_lang"),
        reply_markup=lang_keyboard(),
    )


# ── /lang — re-open language picker ──────────────────────────────────────────

async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        t("select_lang"),
        reply_markup=lang_keyboard(),
    )


# ── Language selection callback ───────────────────────────────────────────────

async def handle_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = query.data.split(":", 1)[1]          # "ru" or "uz"
    ctx.user_data["lang"] = lang

    name = update.effective_user.first_name or ("друг" if lang == "ru" else "do'st")

    # Update the language-picker message to a welcome message
    await query.edit_message_text(
        t("welcome", lang, name=name),
        parse_mode="HTML",
    )

    # Send the appropriate ReplyKeyboard
    markup = staff_menu(lang) if _is_staff(ctx) else main_menu(lang)
    await query.message.reply_text("👇", reply_markup=markup)


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang(ctx)
    await update.message.reply_text(t("help_text", lang), parse_mode="HTML")


# ── /cancel — global escape ───────────────────────────────────────────────────

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lang   = _lang(ctx)
    markup = staff_menu(lang) if _is_staff(ctx) else main_menu(lang)
    await update.message.reply_text(t("cancelled", lang), reply_markup=markup)


# ── 🏠 Main Menu button ───────────────────────────────────────────────────────

async def go_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lang   = _lang(ctx)
    markup = staff_menu(lang) if _is_staff(ctx) else main_menu(lang)
    await update.message.reply_text(
        t("welcome", lang, name=update.effective_user.first_name or ""),
        parse_mode="HTML",
        reply_markup=markup,
    )


# ── 🌐 Language button (from ReplyKeyboard) ──────────────────────────────────

async def change_lang_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(t("select_lang"), reply_markup=lang_keyboard())


# ── Application ───────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set — check your .env file")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Commands ──────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("lang",   cmd_lang))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # ── Language selection callback ───────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_lang, pattern="^lang:"))

    # ── Navigation buttons (simple message handlers, no conversation state) ───
    # These must be registered BEFORE ConversationHandlers so they always fire.
    app.add_handler(MessageHandler(filters.Regex("🏠"), go_home))
    app.add_handler(MessageHandler(filters.Regex("🌐"), change_lang_btn))
    app.add_handler(MessageHandler(filters.Regex("🚪"), staff_logout))
    app.add_handler(MessageHandler(filters.Regex("📋"), view_queue))

    # ── Staff conversation handlers ───────────────────────────────────────────
    for h in staff_handlers():
        app.add_handler(h)

    # ── Customer conversation handler ─────────────────────────────────────────
    app.add_handler(customer_handler())

    logger.info("Bot starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
