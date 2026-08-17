"""
Курс TON (GRAM) до USD - тільки для відображення в шапці Mini App, ніде
більше не використовується (боту для розрахунків курс не потрібен, усе
там у TON). Кешується на кілька хвилин, щоб не смикати зовнішнє API часто.

Джерело - CoinGecko public API (без ключа). Пробуємо кілька можливих
ідентифікаторів монети, бо після перейменування TON -> GRAM (15.06.2026)
не гарантовано, під яким id монета лишилась на CoinGecko.
"""
from __future__ import annotations

import logging
import time

import aiohttp

log = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 5 * 60
_cache: dict = {"price": None, "ts": 0}

_CANDIDATE_IDS = ["the-open-network", "toncoin", "gram"]


async def get_ton_usd_price() -> float | None:
    now = time.time()
    if _cache["price"] is not None and (now - _cache["ts"]) < _CACHE_TTL_SECONDS:
        return _cache["price"]

    for coin_id in _CANDIDATE_IDS:
        try:
            url = (
                "https://api.coingecko.com/api/v3/simple/price"
                f"?ids={coin_id}&vs_currencies=usd"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    price = data.get(coin_id, {}).get("usd")
                    if price:
                        _cache["price"] = float(price)
                        _cache["ts"] = now
                        return _cache["price"]
        except Exception:
            log.debug("Не вдалось отримати курс за id '%s'", coin_id, exc_info=True)
            continue

    log.warning("Не вдалось отримати курс TON/GRAM жодним з відомих id.")
    return None
