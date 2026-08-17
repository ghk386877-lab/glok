"""
Снайпінг по рідкості: шукає лістинги, виставлені за "звичайною" ціною
(близько до floor), але з рідкісною комбінацією model/symbol/backdrop -
тобто потенційно недооцінені відносно свого rarity_per_mille.

Логіка:
1. Тягнемо N найдешевших активних лістингів колекції (search_listings,
   sort="price_asc").
2. Для кожного рахуємо "rarity score" = сума rarity_per_mille по
   model+symbol+backdrop (менше значення = рідкісніша комбінація).
3. Рахуємо медіану rarity score по всій вибірці.
4. Позначаємо як "снайп", якщо:
   - ціна лота близька до floor (не більше SNIPE_PRICE_MARGIN_PCT% дорожча)
   - rarity score помітно нижчий за медіану (тобто рідкісніший за типовий
     лот у цій ціновій категорії) - поріг SNIPE_RARITY_RATIO
"""
from __future__ import annotations

import asyncio

import config
import portals_client
import storage

SNIPE_PRICE_MARGIN_PCT = 15    # лот вважається "близьким до floor", якщо не дорожчий за floor+15%
SNIPE_RARITY_RATIO = 0.5       # rarity лота має бути <= 50% медіани вибірки, щоб рахуватись рідкісним


def _rarity_score(item: dict) -> float | None:
    """Сума rarity_per_mille по model/symbol/backdrop. None, якщо даних немає."""
    attrs = item.get("attributes") or []
    values = [a["rarity_per_mille"] for a in attrs if a.get("rarity_per_mille") is not None]
    if not values:
        return None
    return sum(values)


def _attr_value(item: dict, attr_type: str) -> str | None:
    for a in item.get("attributes") or []:
        if a.get("type") == attr_type:
            return a.get("value")
    return None


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


async def find_snipes_in_collection(gift_name: str, sample_size: int = 40) -> list[dict]:
    """
    Повертає список знайдених "снайпів" для однієї колекції, найкращі
    (найрідкісніші відносно ціни) першими. Порожній список - нічого не
    знайдено (це нормально, не помилка).
    """
    collection_id = await storage.get_collection_id(gift_name)
    if not collection_id:
        raise portals_client.PortalsError(
            f"Не знайшов collection_id для '{gift_name}' - зачекай опитування або перевір назву."
        )

    listings = await portals_client.search_listings(
        collection_id, sort="price_asc", limit=sample_size
    )
    if not listings:
        return []

    floor_price = float(listings[0]["price"])
    scored = []
    for item in listings:
        rarity = _rarity_score(item)
        if rarity is None:
            continue
        scored.append((item, float(item["price"]), rarity))

    if len(scored) < 5:
        return []  # замало даних, щоб рахувати медіану надійно

    median_rarity = _median([s[2] for s in scored])
    price_ceiling = floor_price * (1 + SNIPE_PRICE_MARGIN_PCT / 100)
    rarity_ceiling = median_rarity * SNIPE_RARITY_RATIO

    snipes = []
    for item, price, rarity in scored:
        if price <= price_ceiling and rarity <= rarity_ceiling:
            snipes.append(
                {
                    "tg_id": item.get("tg_id"),
                    "price": price,
                    "floor_price": floor_price,
                    "rarity_score": rarity,
                    "median_rarity": median_rarity,
                    "model": _attr_value(item, "model"),
                    "symbol": _attr_value(item, "symbol"),
                    "backdrop": _attr_value(item, "backdrop"),
                }
            )

    # найрідкісніші (найменший rarity_score відносно медіани) - першими
    snipes.sort(key=lambda s: s["rarity_score"])
    return snipes


async def build_snipe_report(gift_name: str) -> str:
    try:
        snipes = await find_snipes_in_collection(gift_name)
    except portals_client.PortalsError as e:
        return f"Помилка: {e}"

    if not snipes:
        return (
            f"У '{gift_name}' зараз не знайшов недооцінених по рідкості лотів "
            f"(перевірено найдешевші лістинги)."
        )

    lines = [f"\U0001f3af Снайпи по рідкості в '{gift_name}':\n"]
    for s in snipes[:10]:
        ratio = s["rarity_score"] / s["median_rarity"] if s["median_rarity"] else 0
        lines.append(
            f"\u2022 {s['tg_id']}: {s['price']:.2f} TON (floor {s['floor_price']:.2f})\n"
            f"   {s['model']} / {s['symbol']} / {s['backdrop']} - "
            f"rarity {s['rarity_score']:.1f}\u2030 (медіана вибірки {s['median_rarity']:.1f}\u2030, "
            f"у {1/ratio:.1f}x рідкісніше типового)"
        )
    lines.append(
        "\n\u2139\ufe0f Це евристика за rarity_per_mille, не гарантія попиту - "
        "рідкісна комбінація не завжди означає, що хтось захоче купити дорожче."
    )
    return "\n".join(lines)


async def _scan_one(sem: asyncio.Semaphore, name: str):
    async with sem:
        try:
            snipes = await find_snipes_in_collection(name, sample_size=25)
        except portals_client.PortalsAuthError:
            return "auth_error"
        except portals_client.PortalsError:
            return []
        for s in snipes:
            s["gift_name"] = name
        return snipes


async def build_snipe_top_report(gift_names: list[str], top_n: int | None = None) -> str:
    """Сканує кілька колекцій одразу (паралельно, з обмеженням) і показує
    найкращі знахідки по всіх них разом. Якщо authData протух саме для
    цих ендпоінтів - пробує сам оновити токен і повторити один раз."""
    top_n = top_n or config.TOP_N_DISPLAY

    async def _run_batch():
        sem = asyncio.Semaphore(config.API_CONCURRENCY_LIMIT)
        return await asyncio.gather(*(_scan_one(sem, name) for name in gift_names))

    raw = await _run_batch()
    auth_errors = sum(1 for r in raw if r == "auth_error")
    all_snipes = [s for lst in raw if isinstance(lst, list) for s in lst]

    if not all_snipes and auth_errors > 0:
        import portals_auth

        refreshed = await portals_auth.refresh()
        if refreshed:
            raw = await _run_batch()
            auth_errors = sum(1 for r in raw if r == "auth_error")
            all_snipes = [s for lst in raw if isinstance(lst, list) for s in lst]

    if not all_snipes:
        if auth_errors > 0:
            return (
                "\u26a0\ufe0f authData протух саме для ендпоінтів пошуку лістингів, "
                "і автоматичне відновлення не допомогло. Спробуй /refreshauth вручну."
            )
        return "Не знайшов жодного снайпу по рідкості серед перевірених ліквідних колекцій."

    all_snipes.sort(key=lambda s: s["rarity_score"] / (s["median_rarity"] or 1))

    lines = ["\U0001f3af Топ снайпів по рідкості (усі перевірені колекції):\n"]
    for s in all_snipes[:top_n]:
        ratio = s["rarity_score"] / s["median_rarity"] if s["median_rarity"] else 0
        lines.append(
            f"\u2022 {s['gift_name']} {s['tg_id']}: {s['price']:.2f} TON \u2192 "
            f"{s['model']}/{s['symbol']}/{s['backdrop']}, "
            f"у {1/ratio:.1f}x рідкісніше типового лоту"
        )
    return "\n".join(lines)
