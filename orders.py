"""
Звіти по офер-ордерах: різниця між floor-ціною (продаж) і найкращим
поточним офером на купівлю, з урахуванням комісії Portals (продавець
отримує offer.amount мінус комісія, коли продає в офер).
"""
from __future__ import annotations

import asyncio

import config
import portals_client
import storage


async def build_order_report(gift_name: str) -> str:
    collection_id = await storage.get_collection_id(gift_name)
    if not collection_id:
        similar = await storage.find_gift_names(gift_name)
        if similar:
            options = ", ".join(similar[:10])
            return (
                f"Не знайшов точної назви '{gift_name}'. Схожі варіанти: {options}\n"
                f"Спробуй /orders з точною назвою з цього списку."
            )
        return (
            f"Не знайшов '{gift_name}'. Перевір назву (така, як у /floors), "
            f"або зачекай першого опитування, якщо бот щойно запущений."
        )

    try:
        offer = await portals_client.get_top_offer(collection_id)
    except portals_client.PortalsError as e:
        return f"Помилка: {e}"

    if offer is None:
        return f"'{gift_name}': офери на купівлю зараз відсутні (0 активних)."

    floor = offer["floor_price"]
    amount = offer["amount"]
    net_floor_sale = floor * (1 - config.PORTALS_FEE_PERCENT / 100)
    spread = floor - amount
    profit = net_floor_sale - amount
    pct = (spread / floor * 100) if floor else 0

    lines = [
        f"\U0001f4b5 Ордери на '{gift_name}':\n",
        f"Найкращий офер (купівля через офер): {amount:.2f} TON",
        f"Floor-ціна (продаж по floor): {floor:.2f} TON",
        f"Сирий спред: {spread:+.2f} TON ({pct:+.1f}%)",
        f"\nЯкщо купити через цей офер і продати по floor (мінус комісія Portals {config.PORTALS_FEE_PERCENT:.0f}%):",
        f"Отримаєш за продаж по floor: {net_floor_sale:.2f} TON",
        f"Реальний прибуток: {profit:+.2f} TON",
        f"\nАктивних оферів на цю колекцію: {offer['total_count']}",
    ]
    if profit > 0:
        lines.append(
            "\n\u2705 Прибутково навіть з урахуванням комісії."
        )
    return "\n".join(lines)


async def _fetch_offer_profit(sem: asyncio.Semaphore, name: str):
    """Один подарунок: тягне офер і рахує прибуток. Обмежено семафором,
    щоб не перевантажувати Portals API одночасними запитами."""
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
        return (name, amount, floor, profit)


async def build_profit_ranked_report(gift_names: list[str], top_n: int | None = None) -> str:
    """
    Рахує прибуток (купівля через офер -> продаж по floor, з комісією Portals)
    по всіх переданих подарунках ПАРАЛЕЛЬНО (з обмеженням одночасних запитів,
    config.API_CONCURRENCY_LIMIT), і показує TOP-N за прибутком.
    """
    top_n = top_n or config.TOP_N_DISPLAY
    sem = asyncio.Semaphore(config.API_CONCURRENCY_LIMIT)
    raw = await asyncio.gather(*(_fetch_offer_profit(sem, name) for name in gift_names))
    results = [r for r in raw if r is not None]

    if not results:
        return (
            "Не знайшов жодного валідного подарунка з активними оферами "
            f"(поріг ліквідності: \u2265{config.MIN_SALES_24H_FOR_VALID} продажів/24г)."
        )

    results.sort(key=lambda r: r[3], reverse=True)

    lines = [
        f"\U0001f4b0 Топ подарунків за можливим прибутком "
        f"(офер \u2192 floor, після комісії {config.PORTALS_FEE_PERCENT:.0f}%):\n"
    ]
    for name, amount, floor, profit in results[:top_n]:
        sign = "\U0001f7e2" if profit > 0 else "\u26aa"
        lines.append(
            f"{sign} {name}: офер {amount:.2f} \u2192 floor {floor:.2f} TON, "
            f"прибуток {profit:+.2f} TON"
        )
    return "\n".join(lines)
    """
    Спред по кількох подарунках одразу (наприклад, топ-N за обсягом торгів).
    Кожен подарунок - окремий API-запит, тому список має бути коротким
    (щоб не наштовхнутись на rate limit Portals).
    """
    lines = ["\U0001f4b5 Спред floor/офер по топових подарунках:\n"]
    for i, name in enumerate(gift_names):
        if i > 0:
            # невелика пауза між запитами, щоб не впертись у rate limit Portals (429)
            await asyncio.sleep(1.5)

        collection_id = await storage.get_collection_id(name)
        if not collection_id:
            continue
        try:
            offer = await portals_client.get_top_offer(collection_id)
        except portals_client.PortalsError as e:
            lines.append(f"• {name}: помилка ({e})")
            continue
        if offer is None:
            lines.append(f"• {name}: оферів немає")
            continue
        floor = offer["floor_price"]
        amount = offer["amount"]
        net_floor_sale = floor * (1 - config.PORTALS_FEE_PERCENT / 100)
        profit = net_floor_sale - amount
        sign = "\U0001f7e2" if profit > 0 else "\u26aa"
        lines.append(
            f"{sign} {name}: офер {amount:.2f} / floor {floor:.2f} TON \u2192 "
            f"прибуток після комісії {profit:+.2f} TON"
        )
    return "\n".join(lines)
