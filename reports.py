"""
Формування текстових звітів для команд бота на основі даних зі storage.py.
"""
from __future__ import annotations

import config
import storage

DAY_SECONDS = 24 * 60 * 60


def _fmt_change(current: float, previous: float | None) -> str:
    if previous is None or previous == 0:
        return "н/д"
    pct = (current - previous) / previous * 100
    arrow = "\u25b2" if pct > 0 else ("\u25bc" if pct < 0 else "\u25b6")
    return f"{arrow} {pct:+.1f}%"


async def build_floors_report(limit: int = 30) -> str:
    names = await storage.get_all_latest_gift_names()
    rows = []
    for name in names:
        latest = await storage.get_latest(name)
        if not latest:
            continue
        day_ago = await storage.get_snapshot_before(name, DAY_SECONDS)
        change = _fmt_change(latest["floor_price"], day_ago["floor_price"] if day_ago else None)
        rows.append((name, latest["floor_price"], change))

    if not rows:
        return "Ще немає даних - зачекай перше опитування (див. POLL_INTERVAL_SECONDS)."

    rows.sort(key=lambda r: r[1])
    lines = ["\U0001f4ca Floor-ціни (TON) і зміна за 24 год:\n"]
    for name, floor, change in rows[:limit]:
        lines.append(f"• {name}: {floor:.2f} TON  ({change})")
    return "\n".join(lines)


async def build_volume_report(limit: int = 15) -> str:
    names = await storage.get_all_latest_gift_names()
    rows = []
    for name in names:
        latest = await storage.get_latest(name)
        if not latest or latest["volume_24h"] is None:
            continue
        rows.append((name, latest["volume_24h"], latest["floor_price"], latest["sales_24h_count"]))

    if not rows:
        return "Даних про об'єм торгів поки немає."

    rows.sort(key=lambda r: r[1], reverse=True)
    lines = ["\U0001f525 Топ подарунків за об'ємом торгів (24 год):\n"]
    for name, volume, floor, sales_count in rows[:limit]:
        sales_txt = f", {sales_count} угод" if sales_count is not None else ""
        lines.append(f"• {name}: {volume:.1f} TON обороту{sales_txt}, floor {floor:.2f} TON")
    return "\n".join(lines)


async def build_range_report(range_key: str, limit: int = 40) -> str:
    if range_key not in config.PRICE_RANGES:
        available = ", ".join(config.PRICE_RANGES.keys())
        return f"Невідомий діапазон. Доступні: {available}"

    low, high = config.PRICE_RANGES[range_key]
    names = await storage.get_all_latest_gift_names()
    rows = []
    for name in names:
        latest = await storage.get_latest(name)
        if not latest:
            continue
        if low <= latest["floor_price"] < high:
            day_ago = await storage.get_snapshot_before(name, DAY_SECONDS)
            change = _fmt_change(latest["floor_price"], day_ago["floor_price"] if day_ago else None)
            rows.append((name, latest["floor_price"], latest["volume_24h"], change))

    if not rows:
        return f"У діапазоні {low}-{high} TON зараз нічого немає."

    rows.sort(key=lambda r: r[1])
    lines = [f"\U0001f4b0 Подарунки у діапазоні {low}-{high} TON:\n"]
    for name, floor, volume, change in rows[:limit]:
        vol_txt = f"{volume:.1f} TON/24г" if volume is not None else "н/д"
        lines.append(f"• {name}: {floor:.2f} TON  ({change})  об'єм: {vol_txt}")
    return "\n".join(lines)
