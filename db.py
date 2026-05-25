"""
Supabase REST API wrapper — all async, no SDK dependency.
Every function returns plain dicts / lists matching the existing CRM schema.
"""
import time
import httpx
from config import SUPABASE_URL, SUPABASE_KEY, SERVICES


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base(table: str) -> str:
    return f"{SUPABASE_URL}/{table}"


# ── Queue helpers ────────────────────────────────────────────────────────────

async def get_active_queue() -> list[dict]:
    """All bookings not yet done, ordered oldest-first (queue position)."""
    async with httpx.AsyncClient() as c:
        r = await c.get(
            _base("bookings"),
            headers=_headers(),
            params={
                "workflow_status": "neq.done",
                "order": "created_at.asc",
                "select": "*",
            },
        )
        r.raise_for_status()
        return r.json()


async def get_booking_by_plate(plate: str) -> dict | None:
    """Latest active (non-done) booking for the given plate."""
    async with httpx.AsyncClient() as c:
        r = await c.get(
            _base("bookings"),
            headers=_headers(),
            params={
                "plate": f"eq.{plate.upper()}",
                "workflow_status": "neq.done",
                "order": "created_at.desc",
                "limit": "1",
                "select": "*",
            },
        )
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None


async def get_all_active_plates() -> list[dict]:
    """Minimal list of active bookings for staff pick-lists."""
    async with httpx.AsyncClient() as c:
        r = await c.get(
            _base("bookings"),
            headers=_headers(),
            params={
                "workflow_status": "neq.done",
                "order": "created_at.asc",
                "select": "id,plate,workflow_status,payment_status",
            },
        )
        r.raise_for_status()
        return r.json()


# ── Mutations ────────────────────────────────────────────────────────────────

async def add_booking(plate: str, service_key: str, payment_type: str = "cash") -> str:
    """
    Insert a new booking and a matching payments row.
    Returns the generated booking id.
    """
    svc = SERVICES.get(service_key, {})
    booking_id = f"TG{int(time.time() * 1000) % 100_000_000:08d}"

    booking_row = {
        "id":              booking_id,
        "plate":           plate.upper(),
        "brand":           "",
        "model":           "",
        "service":         service_key,
        "amount":          svc.get("price", 0),
        "payment_status":  "not-paid",
        "workflow_status": "queue",
    }

    payment_row = {
        "booking_id": booking_id,
        "plate":      plate.upper(),
        "amount":     svc.get("price", 0),
        "status":     "not-paid",
    }

    async with httpx.AsyncClient() as c:
        r = await c.post(_base("bookings"), headers=_headers(), json=booking_row)
        r.raise_for_status()
        # Try to insert payment; ignore duplicate-key errors
        await c.post(_base("payments"), headers=_headers(), json=payment_row)
        # Upsert loyalty (increment visits)
        await _increment_loyalty(c, plate.upper(), svc.get("price", 0))

    return booking_id


async def update_workflow_status(booking_id: str, status: str) -> bool:
    async with httpx.AsyncClient() as c:
        r = await c.patch(
            _base("bookings"),
            headers=_headers(),
            params={"id": f"eq.{booking_id}"},
            json={"workflow_status": status},
        )
        return r.status_code in (200, 204)


async def update_payment_status(booking_id: str, status: str) -> bool:
    async with httpx.AsyncClient() as c:
        r1 = await c.patch(
            _base("bookings"),
            headers=_headers(),
            params={"id": f"eq.{booking_id}"},
            json={"payment_status": status},
        )
        await c.patch(
            _base("payments"),
            headers=_headers(),
            params={"booking_id": f"eq.{booking_id}"},
            json={"status": status},
        )
        return r1.status_code in (200, 204)


async def get_loyalty(plate: str) -> dict | None:
    async with httpx.AsyncClient() as c:
        r = await c.get(
            _base("loyalty"),
            headers=_headers(),
            params={"plate": f"eq.{plate.upper()}", "select": "*"},
        )
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None


# ── Internal helpers ─────────────────────────────────────────────────────────

async def _increment_loyalty(client: httpx.AsyncClient, plate: str, amount: int) -> None:
    r = await client.get(
        _base("loyalty"),
        headers=_headers(),
        params={"plate": f"eq.{plate}", "select": "*"},
    )
    existing = r.json()
    points_earned = amount // 10_000

    if existing:
        row = existing[0]
        await client.patch(
            _base("loyalty"),
            headers=_headers(),
            params={"plate": f"eq.{plate}"},
            json={
                "visits":      row["visits"] + 1,
                "total_spent": row["total_spent"] + amount,
                "points":      row["points"] + points_earned,
            },
        )
    else:
        tier = _get_tier(1)
        await client.post(
            _base("loyalty"),
            headers=_headers(),
            json={
                "plate":       plate,
                "visits":      1,
                "total_spent": amount,
                "points":      points_earned,
                "tier":        tier,
            },
        )


def _get_tier(visits: int) -> str:
    if visits >= 50: return "💎 VIP"
    if visits >= 25: return "🥇 Gold"
    if visits >= 10: return "🥈 Silver"
    return "🥉 Bronze"


def queue_position(queue: list[dict], booking_id: str) -> int:
    """1-based position in the active queue."""
    for i, b in enumerate(queue):
        if b["id"] == booking_id:
            return i + 1
    return -1
