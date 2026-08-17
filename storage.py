"""
Зберігаємо знімки floor-ціни/об'єму/кількості угод по кожному подарунку
з часовою міткою. Це дає змогу порахувати % зміни ціни за будь-який період
(наприклад, "за останні ~24 години").

Поля floor_price/volume_24h/sales_24h_count відповідають реальним полям
Portals API: floor_price, day_volume, sales_24h_count (підтверджено через
debug_inspect.py 09.07.2026).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS floor_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gift_name TEXT NOT NULL,
    floor_price REAL NOT NULL,
    volume_24h REAL,
    sales_24h_count INTEGER,
    ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_gift_ts
    ON floor_snapshots (gift_name, ts);

CREATE TABLE IF NOT EXISTS subscriptions (
    chat_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS collection_meta (
    gift_name TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL
);
"""


@asynccontextmanager
async def _db():
    conn = await aiosqlite.connect(config.DB_PATH)
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    async with _db() as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()
        # міграція: якщо база створена старішою версією коду без якогось поля -
        # додаємо його, замість того щоб змушувати видаляти portals.db вручну.
        cur = await conn.execute("PRAGMA table_info(floor_snapshots)")
        existing_cols = {row[1] for row in await cur.fetchall()}
        if "sales_24h_count" not in existing_cols:
            await conn.execute(
                "ALTER TABLE floor_snapshots ADD COLUMN sales_24h_count INTEGER"
            )
            await conn.commit()


async def save_snapshot(
    gift_name: str,
    floor_price: float,
    volume_24h: float | None,
    sales_24h_count: int | None = None,
) -> None:
    async with _db() as conn:
        await conn.execute(
            "INSERT INTO floor_snapshots "
            "(gift_name, floor_price, volume_24h, sales_24h_count, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (gift_name, floor_price, volume_24h, sales_24h_count, int(time.time())),
        )
        await conn.commit()


async def get_latest(gift_name: str) -> dict[str, Any] | None:
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT floor_price, volume_24h, sales_24h_count, ts FROM floor_snapshots "
            "WHERE gift_name = ? ORDER BY ts DESC LIMIT 1",
            (gift_name,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "floor_price": row[0],
            "volume_24h": row[1],
            "sales_24h_count": row[2],
            "ts": row[3],
        }


async def get_snapshot_before(gift_name: str, max_age_seconds: int) -> dict[str, Any] | None:
    """
    Знаходить найближчий знімок, зроблений щонайменше `max_age_seconds` тому -
    саме він потрібен, щоб порахувати "зміна ціни за 24 год".
    """
    cutoff = int(time.time()) - max_age_seconds
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT floor_price, volume_24h, sales_24h_count, ts FROM floor_snapshots "
            "WHERE gift_name = ? AND ts <= ? ORDER BY ts DESC LIMIT 1",
            (gift_name, cutoff),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "floor_price": row[0],
            "volume_24h": row[1],
            "sales_24h_count": row[2],
            "ts": row[3],
        }


async def get_all_latest_gift_names() -> list[str]:
    async with _db() as conn:
        cur = await conn.execute("SELECT DISTINCT gift_name FROM floor_snapshots")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def prune_older_than(seconds: int) -> None:
    """Прибирає надто старі знімки, щоб база не росла нескінченно."""
    cutoff = int(time.time()) - seconds
    async with _db() as conn:
        await conn.execute("DELETE FROM floor_snapshots WHERE ts < ?", (cutoff,))
        await conn.commit()


async def add_subscription(chat_id: int) -> None:
    async with _db() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO subscriptions (chat_id) VALUES (?)", (chat_id,)
        )
        await conn.commit()


async def remove_subscription(chat_id: int) -> None:
    async with _db() as conn:
        await conn.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
        await conn.commit()


async def get_subscriptions() -> list[int]:
    async with _db() as conn:
        cur = await conn.execute("SELECT chat_id FROM subscriptions")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def is_subscribed(chat_id: int) -> bool:
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM subscriptions WHERE chat_id = ?", (chat_id,)
        )
        return (await cur.fetchone()) is not None


async def save_collection_id(gift_name: str, collection_id: str) -> None:
    """
    Кешуємо реальний collection_id з collections() (не з бібліотеки!) -
    потрібен для запиту офер-даних напряму, в обхід застарілого
    захардкодженого словника aportalsmp.offers.collections_ids.
    """
    async with _db() as conn:
        await conn.execute(
            "INSERT INTO collection_meta (gift_name, collection_id) VALUES (?, ?) "
            "ON CONFLICT(gift_name) DO UPDATE SET collection_id = excluded.collection_id",
            (gift_name, collection_id),
        )
        await conn.commit()


async def get_collection_id(gift_name: str) -> str | None:
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT collection_id FROM collection_meta WHERE gift_name = ?", (gift_name,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def find_gift_names(query: str, limit: int = 10) -> list[str]:
    """Пошук назв подарунків за частковим збігом - для /orders з нечіткою назвою."""
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT DISTINCT gift_name FROM collection_meta WHERE gift_name LIKE ? LIMIT ?",
            (f"%{query}%", limit),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]
