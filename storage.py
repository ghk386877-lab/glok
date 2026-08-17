"""
Зберігаємо знімки floor-ціни/об'єму/кількості угод по кожному подарунку
з часовою міткою. Це дає змогу порахувати % зміни ціни за будь-який період
(наприклад, "за останні ~24 години").

Поля floor_price/volume_24h/sales_24h_count відповідають реальним полям
Portals API: floor_price, day_volume, sales_24h_count (підтверджено через
debug_inspect.py 09.07.2026).
"""
from __future__ import annotations

import os
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

CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    gift_name TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL,
    buy_ts INTEGER NOT NULL,
    sell_ts INTEGER
);
CREATE INDEX IF NOT EXISTS idx_portfolio_chat ON portfolio (chat_id);
"""


@asynccontextmanager
async def _db():
    # запобіжник: якщо батьківська папка DB_PATH (напр. /data) чомусь не
    # існує - SQLite сам її не створить і впаде з "unable to open database
    # file". Створюємо заздалегідь. Це НЕ замінює потребу в реальному
    # Railway Volume для збереження даних між редеплоями - без volume
    # папка створиться в ефемерній файловій системі і дані все одно
    # зникнуть при наступному редеплої, просто бот хоча б не впаде.
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
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


async def add_purchase(chat_id: int, gift_name: str, buy_price: float) -> int:
    async with _db() as conn:
        cur = await conn.execute(
            "INSERT INTO portfolio (chat_id, gift_name, buy_price, buy_ts) VALUES (?, ?, ?, ?)",
            (chat_id, gift_name, buy_price, int(time.time())),
        )
        await conn.commit()
        return cur.lastrowid


async def close_oldest_open(chat_id: int, gift_name: str, sell_price: float) -> dict | None:
    """Закриває НАЙСТАРІШУ відкриту позицію по цій назві (FIFO). None, якщо
    відкритої позиції з такою назвою немає."""
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT id, buy_price FROM portfolio WHERE chat_id = ? AND gift_name = ? "
            "AND sell_price IS NULL ORDER BY buy_ts ASC LIMIT 1",
            (chat_id, gift_name),
        )
        row = await cur.fetchone()
        if not row:
            return None
        trade_id, buy_price = row
        await conn.execute(
            "UPDATE portfolio SET sell_price = ?, sell_ts = ? WHERE id = ?",
            (sell_price, int(time.time()), trade_id),
        )
        await conn.commit()
        return {
            "id": trade_id,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "profit": sell_price - buy_price,
        }


async def get_open_positions(chat_id: int) -> list[dict]:
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT id, gift_name, buy_price, buy_ts FROM portfolio "
            "WHERE chat_id = ? AND sell_price IS NULL ORDER BY buy_ts DESC",
            (chat_id,),
        )
        rows = await cur.fetchall()
        return [
            {"id": r[0], "gift_name": r[1], "buy_price": r[2], "buy_ts": r[3]} for r in rows
        ]


async def get_closed_trades(chat_id: int) -> list[dict]:
    async with _db() as conn:
        cur = await conn.execute(
            "SELECT id, gift_name, buy_price, sell_price, buy_ts, sell_ts FROM portfolio "
            "WHERE chat_id = ? AND sell_price IS NOT NULL ORDER BY sell_ts DESC",
            (chat_id,),
        )
        rows = await cur.fetchall()
        return [
            {
                "id": r[0],
                "gift_name": r[1],
                "buy_price": r[2],
                "sell_price": r[3],
                "buy_ts": r[4],
                "sell_ts": r[5],
                "profit": r[3] - r[2],
            }
            for r in rows
        ]


async def delete_trade(chat_id: int, trade_id: int) -> bool:
    async with _db() as conn:
        cur = await conn.execute(
            "DELETE FROM portfolio WHERE id = ? AND chat_id = ?", (trade_id, chat_id)
        )
        await conn.commit()
        return cur.rowcount > 0
