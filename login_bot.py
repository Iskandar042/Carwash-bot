"""
"Login via Telegram" backend for the OWNER bot (@Autowash_owner_bot).
Deep link t.me/<owner_bot>?start=lg_<token> -> confirm button -> claim_web_login().
On Render it also opens a tiny HTTP port so the Web Service deploy stays healthy.
Env: LOGIN_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY (service_role / secret key).
"""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import SUPABASE_URL, SUPABASE_KEY

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s", level=logging.INFO
)
logger = logging.getLogger("login_bot")

LOGIN_BOT_TOKEN = os.getenv("LOGIN_BOT_TOKEN", "")


def _start_keep_alive_server() -> None:
    """Render Web Services need an open HTTP port; this bot uses polling, so
    bind $PORT with a tiny health endpoint to keep the deploy healthy."""
    port = int(os.getenv("PORT", "10000"))

    class _Ping(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", port), _Ping).serve_forever(),
        daemon=True,
    ).start()
    logger.info("Keep-alive HTTP server listening on port %s", port)


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
    _start_keep_alive_server()   # bind $PORT so Render's Web Service stays healthy
    app = Application.builder().token(LOGIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_weblogin, pattern="^weblogin:"))
    logger.info("Login bot starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
