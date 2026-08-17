"""
Обгортка над amrkt.MarketClient.

На відміну від Portals/Tonnel (де authData - це короткий рядок на кожен
запит), MRKT-клієнт тримає ПОСТІЙНЕ з'єднання (Pyrogram-сесія). Тому
підключаємось ОДИН РАЗ при старті бота (main.py викликає connect()) і
перевикористовуємо це з'єднання для всіх запитів, замість того щоб
відкривати нову Telegram-сесію на кожен виклик.
"""
from __future__ import annotations

import logging
from typing import Any

import config

log = logging.getLogger(__name__)

_client = None
NANO = 1_000_000_000  # sale_price в amrkt - у нано-TON


class MrktError(RuntimeError):
    pass


async def connect() -> None:
    """Викликати один раз при старті бота (main.py)."""
    global _client
    if _client is not None:
        return
    if not config.MRKT_API_ID or not config.MRKT_API_HASH:
        log.warning(
            "MRKT_API_ID/MRKT_API_HASH не задані в .env - MRKT інтеграція вимкнена "
            "(арбітраж і /arbitrage працювати не будуть, поки не заповниш і не "
            "виконаєш setup_mrkt.py)."
        )
        return

    from amrkt import MarketClient

    client = MarketClient(
        api_id=int(config.MRKT_API_ID),
        api_hash=config.MRKT_API_HASH,
        session_name=config.MRKT_SESSION_NAME,
    )
    try:
        await client.__aenter__()
    except Exception:
        log.exception(
            "Не вдалось підключитись до MRKT. Перевір, чи виконаний setup_mrkt.py "
            "і чи існує файл сесії."
        )
        return
    _client = client
    log.info("MRKT: підключено.")


async def disconnect() -> None:
    global _client
    if _client is not None:
        try:
            await _client.__aexit__(None, None, None)
        except Exception:
            log.exception("Помилка при відключенні MRKT-клієнта")
        _client = None


def is_connected() -> bool:
    return _client is not None


async def get_top_order(collection_name: str) -> dict[str, Any] | None:
    """
    Найкращий (найвищий) активний ордер (офер на купівлю) для колекції на
    MRKT. Публічної функції для цього в бібліотеці amrkt немає - йдемо
    напряму до /orders, перевикористовуючи внутрішній токен вже підключеного
    клієнта (client._token). Підтверджено робочим 19.07.2026.

    Повертає {"amount": float, "total_quantity": int} у TON, або None,
    якщо активних ордерів немає.
    """
    if _client is None:
        raise MrktError("MRKT-клієнт не підключено.")

    token = getattr(_client, "_token", None)
    if not token:
        raise MrktError("Не вдалось дістати внутрішній токен MRKT-клієнта.")

    import aiohttp

    url = "https://api.tgmrkt.io/api/v1/orders"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    body = {
        "collectionNames": [collection_name],
        "modelNames": [],
        "backdropNames": [],
        "symbolNames": [],
        "availableForStaking": None,
        "minPrice": None,
        "maxPrice": None,
        "ordering": "Price",
        "lowToHigh": False,
        "query": None,
        "cursor": "",
        "count": 1,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                raise MrktError(f"MRKT API повернув статус {resp.status}")
            data = await resp.json()

    orders = data.get("orders") or []
    if not orders:
        return None
    top = orders[0]
    return {
        "amount": top["priceMaxNanoTONs"] / NANO,
        "total_quantity": top.get("totalQuantity", 1),
    }


async def get_floor(collection_name: str) -> dict[str, Any] | None:
    """
    Floor-ціна на MRKT для колекції - найдешевший активний лістинг
    (search_gifts, сортування за зростанням ціни, перший результат).

    Повертає {"price": float, "price_without_fee": float} у TON,
    або None, якщо активних лістингів немає.
    """
    if _client is None:
        raise MrktError(
            "MRKT-клієнт не підключено (перевір MRKT_API_ID/MRKT_API_HASH в .env "
            "і чи виконаний setup_mrkt.py)."
        )

    result = await _client.search_gifts(
        collection_names=[collection_name],
        count=1,
        ordering="Price",
        low_to_high=True,
    )
    if not result.items:
        return None

    item = result.items[0]
    return {
        "price": item.sale_price / NANO,
        "price_without_fee": item.sale_price_without_fee / NANO,
    }
