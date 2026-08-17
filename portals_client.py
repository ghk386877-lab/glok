"""
Тонка обгортка над бібліотекою aportalsmp.

Довідково: реальний домен маркетплейсу - portal-market.com, а функція
search() з бібліотеки під капотом викликає portal-market.com/api/nfts/search.
Це той самий ендпоінт, на який варто дивитись у DevTools при отриманні authData.

ВАЖЛИВО: бібліотека молода і активно змінюється (це реверс-інжинірингове API,
не офіційне). Якщо після встановлення (`pip install aportalsmp`) назви функцій
або полів у відповідях відрізняються від того, що нижче - онови саме цей файл,
решта бота цього не відчує. Для звірки полів спочатку запусти debug_inspect.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import auth_store

log = logging.getLogger(__name__)

try:
    import aportalsmp
except ImportError:  # даємо боту хоч якось піднятись і показати зрозумілу помилку
    aportalsmp = None


class PortalsError(RuntimeError):
    pass


def _require_lib():
    if aportalsmp is None:
        raise PortalsError(
            "Пакет aportalsmp не встановлено. Виконай: pip install aportalsmp"
        )


def _require_auth() -> str:
    auth = auth_store.get_auth()
    if not auth:
        raise PortalsError(
            "authData не задано. Встанови його командою /setauth <tma ...> "
            "(див. README, розділ 'Як отримати authData')."
        )
    return auth


async def get_collections(limit: int = 200) -> list[dict[str, Any]]:
    """
    Повертає список колекцій подарунків з floor-ціною і обсягом торгів.

    aportalsmp.collections() повертає не список, а об'єкт-обгортку класу
    Collections, реальні дані лежать у приватному атрибуті _collections
    (підтверджено через debug_inspect.py). Кожен елемент - dict такого вигляду:
        {
            "name": "Heroic Helmet",
            "floor_price": "176.47",      # рядок, треба float()
            "day_volume": "1231.07",      # обсяг торгів за 24 год, у TON
            "sales_24h_count": 7,         # кількість угод за 24 год
            "supply": 3432,
            "market_cap": "605645.04",
            ...
        }
    """
    _require_lib()
    auth = _require_auth()
    result = await aportalsmp.collections(limit=limit, authData=auth)
    return getattr(result, "_collections", [])


async def get_top_offer(collection_id: str, _retries: int = 2) -> dict[str, Any] | None:
    """
    Найкращий поточний офер на купівлю для колекції, за реальним collection_id
    (не назвою!). Йдемо напряму до ендпоінта, В ОБХІД aportalsmp.topOffer(),
    бо та функція звіряє назву з захардкодженим словником aportalsmp.offers.collections_ids
    (лише ~105 колекцій, застарілий - підтверджено 10.07.2026), і не знає
    про новіші подарунки на кшталт "Vice Cream".

    Повертає:
        {"amount": float, "floor_price": float, "total_count": int} або None,
        якщо офери на цю колекцію відсутні.
    """
    _require_lib()
    auth = _require_auth()
    import aportalsmp.offers as offers_module

    url = offers_module.API_URL + "collection-offers/" + collection_id + "/top"
    headers = {**offers_module.HEADERS_MAIN, "Authorization": auth}
    response = await offers_module.fetch(
        method="GET", url=url, headers=headers, impersonate="chrome110"
    )

    if response.status_code == 429:
        if _retries <= 0:
            raise PortalsError(
                "Portals API повернув статус 429 (забагато запитів) навіть "
                "після повторних спроб. Зачекай трохи і спробуй ще раз."
            )
        await asyncio.sleep(3)
        return await get_top_offer(collection_id, _retries=_retries - 1)

    if response.status_code == 401:
        raise PortalsError(
            "authData застарів або невалідний для цього запиту (401 auth sign is "
            "invalid). Онови через /setauth свіжим токеном з web.telegram.org."
        )
    if response.status_code != 200:
        raise PortalsError(f"Portals API повернув статус {response.status_code}")

    body = response.json()
    offers = body.get("offers") or []
    if not offers:
        return None

    top = offers[0]
    return {
        "amount": float(top["amount"]),
        "floor_price": float(top["collection"]["floor_price"]),
        "total_count": body.get("total_count", len(offers)),
    }


async def get_market_activity(
    activity_type: str = "buy",
    limit: int = 100,
    gift_name: str | list | None = None,
) -> list[dict[str, Any]]:
    """
    Історія угод. Використовуємо як запасний варіант для підрахунку обсягу
    торгів за 24 год, якщо поле volume_24h в collections() виявиться неточним
    або відсутнім.
    """
    _require_lib()
    auth = _require_auth()
    kwargs: dict[str, Any] = dict(
        sort="latest",
        offset=0,
        limit=limit,
        activityType=activity_type,
        authData=auth,
    )
    if gift_name:
        kwargs["gift_name"] = gift_name
    data = await aportalsmp.marketActivity(**kwargs)
    return data


async def get_floors(gift_name: str) -> dict[str, Any]:
    """Floor-ціни моделей/бекдропів/символів всередині однієї колекції подарунка."""
    _require_lib()
    auth = _require_auth()
    data = await aportalsmp.filterFloors(gift_name=gift_name, authData=auth)
    return data
