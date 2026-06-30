"""
Standalone "Login via Telegram" backend for the OWNER bot (@Leadgram_admin_bot).

The owner web panel opens  t.me/<owner_bot>?start=lg_<token> . This tiny bot
handles that deep link: it shows a confirm button, and on tap it calls the
Supabase RPC claim_web_login() with the user's real Telegram username, which
lets the browser finish logging in.

Run it ALONGSIDE your worker bot (bot.py), with the OWNER bot's token:

    # Windows PowerShell
    $env:LOGIN_BOT_TOKEN="<@Leadgram_admin_bot token from BotFather>"
    python login_bot.py

    # Linux / macOS
    LOGIN_BOT_TOKEN="<token>" python login_bot.py

SUPABASE_URL / SUPABASE_KEY are read from the same .env / config as the main bot
(SUPABASE_KEY must be the service_role key so claim_web_login is allowed).
"""
import logging
import os

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import SUPABASE_URL, SUPABASE_KEY

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s", level=logging.INFO
)
logger = logging.getLogger("login_bot")

LOGIN_BOT_TOKEN = os.getenv("LOGIN_BOT_TOKEN", "")


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args or []
    if args and args[0].startswith("lg_"):
        token = args[0][3:]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Войти / Kirish", callback_data=f"weblogin:{token}")
        ]])
        await update.message.reply_text(
            "🔐 Вход в панель AUTOWASH в браузере.\n"
            "Нажмите кнопку ниже, чтобы войти под своим аккаунтом.\n\n"
            "Brauzerda AUTOWASH panelига kirish. Tasdiqlash uchun tugmani bosing.",
            reply_markup=kb,
        )
        return
    await update.message.reply_text(
        "Это бот входа в панель AUTOWASH. Откройте панель в браузере и нажмите "
        "«Войти через Telegram».\n\n"
        "Bu AUTOWASH panelига kirish boti. Brauzerda panelni oching."
    )


async def handle_weblogin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    token = query.data.split(":", 1)[1]
    user = update.effective_user
    username = user.username or ""

    if not username:
        await query.edit_message_text(
            "⚠️ У вас нет @username в Telegram. Задайте его в настройках и попробуйте снова.\n\n"
            "Telegram'da @username yo'q. Sozlamalardan o'rnating va qayta urinib ko'ring."
        )
        return

    ok = False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{SUPABASE_URL}/rpc/claim_web_login",
                headers=_sb_headers(),
                json={"p_token": token, "p_username": username, "p_tg_id": user.id},
            )
            ok = r.status_code == 200 and bool((r.json() or {}).get("ok"))
    except Exception as e:
        logger.warning("claim_web_login failed: %s", e)

    if ok:
        await query.edit_message_text(
            "✅ Готово! Вернитесь в браузер — вы вошли.\n"
            "✅ Tayyor! Brauzerga qayting — kirdingiz."
        )
    else:
        await query.edit_message_text(
            "⚠️ Ссылка устарела. Обновите страницу входа и попробуйте снова.\n"
            "⚠️ Havola eskirgan. Sahifani yangilab, qayta urinib ko'ring."
        )


def main() -> None:
    if not LOGIN_BOT_TOKEN:
        raise RuntimeError("LOGIN_BOT_TOKEN is not set (the owner bot's token).")
    app = Application.builder().token(LOGIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_weblogin, pattern="^weblogin:"))
    logger.info("Login bot starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
