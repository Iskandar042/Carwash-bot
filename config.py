import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
SUPABASE_URL   = os.getenv("SUPABASE_URL", "https://xiwkqotyhcejzbeymovi.supabase.co")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY", "")
STAFF_PASSWORD = os.getenv("STAFF_PASSWORD", "worker123")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")

# Car wash services — must match CRM dashboard keys
SERVICES: dict[str, dict] = {
    "express":   {"name": "Экспресс мойка",   "price": 50_000,  "dur": 15},
    "premium":   {"name": "Премиум мойка",     "price": 120_000, "dur": 30},
    "deluxe":    {"name": "Делюкс + Воск",     "price": 180_000, "dur": 45},
    "detail":    {"name": "Полная детейлинг",  "price": 400_000, "dur": 120},
    "engine":    {"name": "Чистка двигателя",  "price": 150_000, "dur": 30},
    "headlight": {"name": "Полировка фар",     "price": 130_000, "dur": 45},
}

WORKFLOW_LABELS = {
    "queue":   "⏳ В очереди",
    "washing": "🚿 Моется",
    "done":    "✅ Готово",
}

PAYMENT_LABELS = {
    "not-paid": "❌ Не оплачено",
    "pending":  "⏳ Ожидает оплаты",
    "paid":     "✅ Оплачено",
}
