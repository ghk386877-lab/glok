"""
Дані для Mini App у структурованому вигляді (list[dict]), на відміну від
reports.py/orders.py/arbitrage.py, які форматують текст для Telegram.
Внутрішньо використовує ті самі джерела даних (storage.py, portals_client.py,
mrkt_client.py), просто інший формат виводу.
"""
from __future__ import annotations

import asyncio

import config
import mrkt_client
import portals_client
import storage

DAY_SECONDS = 24 * 60 * 60


async def get_floors() -> list[dict]:
    names = await storage.get_all_latest_gift_names()
    rows = []
    for name in names:
        latest = await storage.get_latest(name)
        if not latest:
            continue
        day_ago = await storage.get_snapshot_before(name, DAY_SECONDS)
        change_pct = None
        if day_ago and day_ago["floor_price"]:
            change_pct = (
                (latest["floor_price"] - day_ago["floor_price"]) / day_ago["floor_price"] * 100
            )
        rows.append(
            {
                "name": name,
                "floor": latest["floor_price"],
                "volume_24h": latest["volume_24h"],
                "sales_24h": latest["sales_24h_count"],
                "change_24h_pct": change_pct,
            }
        )
    rows.sort(key=lambda r: r["floor"])
    return rows


async def get_volume(limit: int = 30) -> list[dict]:
    rows = await get_floors()
    rows = [r for r in rows if r["volume_24h"] is not None]
    rows.sort(key=lambda r: r["volume_24h"], reverse=True)
    return rows[:limit]


async def get_range(range_key: str) -> list[dict]:
    if range_key not in config.PRICE_RANGES:
        return []
    low, high = config.PRICE_RANGES[range_key]
    rows = await get_floors()
    return [r for r in rows if low <= r["floor"] < high]


async def _fetch_offer_row(sem: asyncio.Semaphore, name: str):
    async with sem:
        collection_id = await storage.get_collection_id(name)
        if not collection_id:
            return None
        try:
            offer = await portals_client.get_top_offer(collection_id)
        except portals_client.PortalsError:
            return None
        if offer is None:
            return None
        floor = offer["floor_price"]
        amount = offer["amount"]
        net_floor_sale = floor * (1 - config.PORTALS_FEE_PERCENT / 100)
        profit = net_floor_sale - amount
        return {"name": name, "offer": amount, "floor": floor, "profit": profit}


async def get_orders_top(limit: int | None = None) -> list[dict]:
    limit = limit or config.TOP_N_DISPLAY
    all_rows = await get_floors()
    valid = [r for r in all_rows if (r["sales_24h"] or 0) >= config.MIN_SALES_24H_FOR_VALID]
    valid.sort(key=lambda r: r["volume_24h"] or 0, reverse=True)
    candidates = valid[: config.ORDERS_CANDIDATE_POOL]

    sem = asyncio.Semaphore(config.API_CONCURRENCY_LIMIT)
    raw = await asyncio.gather(*(_fetch_offer_row(sem, row["name"]) for row in candidates))
    results = [r for r in raw if r is not None]
    results.sort(key=lambda r: r["profit"], reverse=True)
    return results[:limit]


async def _fetch_arbitrage_row(sem: asyncio.Semaphore, name: str, portals_floor: float):
    import arbitrage as arb_module

    async with sem:
        try:
            mrkt_offer = await mrkt_client.get_floor(name)
        except mrkt_client.MrktError:
            return None
        if mrkt_offer is None:
            return None
        mrkt_price = mrkt_offer["price"]
        mrkt_price_no_fee = mrkt_offer["price_without_fee"]
        dir1, dir2 = arb_module.compute_both_directions(portals_floor, mrkt_price, mrkt_price_no_fee)
        best = dir1 if dir1.profit > dir2.profit else dir2
        return {
            "name": name,
            "portals_floor": portals_floor,
            "mrkt_price": mrkt_price,
            "buy_on": best.buy_on,
            "profit": best.profit,
        }


async def get_arbitrage_top(limit: int | None = None) -> list[dict]:
    limit = limit or config.TOP_N_DISPLAY
    if not mrkt_client.is_connected():
        return []

    all_rows = await get_floors()
    valid = [r for r in all_rows if (r["sales_24h"] or 0) >= config.MIN_SALES_24H_FOR_VALID]
    valid.sort(key=lambda r: r["volume_24h"] or 0, reverse=True)
    candidates = valid[: config.ARBITRAGE_CANDIDATE_POOL]

    sem = asyncio.Semaphore(config.API_CONCURRENCY_LIMIT)
    raw = await asyncio.gather(
        *(_fetch_arbitrage_row(sem, row["name"], row["floor"]) for row in candidates)
    )
    results = [r for r in raw if r is not None]
    results.sort(key=lambda r: r["profit"], reverse=True)
    return results[:limit]
