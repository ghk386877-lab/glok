"""
Звіти по ордерах на MRKT: купівля по floor -> продаж в найкращий активний
ордер (аналог orders.py для Portals).
"""
from __future__ import annotations

import asyncio

import config
import mrkt_client


def _sell_into_order_net(order_amount: float) -> float:
    """MRKT: покупець (той, хто створив ордер) платить order_amount - це
    вже включає комісію MRKT зверху. Продавець (ти) отримуєш order_amount
    мінус комісія."""
    return order_amount / (1 + config.MRKT_FEE_PERCENT / 100)


async def build_mrkt_order_report(gift_name: str) -> str:
    try:
        floor = await mrkt_client.get_floor(gift_name)
        order = await mrkt_client.get_top_order(gift_name)
    except mrkt_client.MrktError as e:
        return f"Помилка: {e}"

    if floor is None:
        return f"'{gift_name}': активних лістингів на MRKT немає."
    if order is None:
        return f"'{gift_name}': floor {floor['price']:.2f} TON, активних ордерів немає."

    buy_price = floor["price"]
    order_amount = order["amount"]
    net_from_order = _sell_into_order_net(order_amount)
    profit = net_from_order - buy_price

    lines = [
        f"\U0001f4b5 MRKT-ордери на '{gift_name}':\n",
        f"Floor-ціна (купівля): {buy_price:.2f} TON",
        f"Найкращий ордер (сира сума покупця): {order_amount:.2f} TON",
        f"\nЯкщо купити по floor і продати в цей ордер "
        f"(мінус комісія MRKT {config.MRKT_FEE_PERCENT:.0f}%):",
        f"Отримаєш за продаж: {net_from_order:.2f} TON",
        f"Реальний прибуток: {profit:+.2f} TON",
        f"\nКількість позицій в ордері: {order['total_quantity']}",
    ]
    if profit > 0:
        lines.append("\n\u2705 Прибутково навіть з урахуванням комісії.")
    return "\n".join(lines)


async def _fetch_one(sem: asyncio.Semaphore, name: str):
    async with sem:
        try:
            floor = await mrkt_client.get_floor(name)
            order = await mrkt_client.get_top_order(name)
        except mrkt_client.MrktError:
            return None
        if floor is None or order is None:
            return None
        buy_price = floor["price"]
        net_from_order = _sell_into_order_net(order["amount"])
        profit = net_from_order - buy_price
        return (name, buy_price, order["amount"], profit)


async def build_mrkt_order_top_report(gift_names: list[str], top_n: int | None = None) -> str:
    if not mrkt_client.is_connected():
        return "MRKT не підключено."

    top_n = top_n or config.TOP_N_DISPLAY
    sem = asyncio.Semaphore(config.API_CONCURRENCY_LIMIT)
    raw = await asyncio.gather(*(_fetch_one(sem, name) for name in gift_names))
    results = [r for r in raw if r is not None]

    if not results:
        return "Не знайшов подарунків з одночасно floor і активним ордером на MRKT."

    results.sort(key=lambda r: r[3], reverse=True)

    lines = [
        f"\U0001f4b5 Топ MRKT-ордерів за прибутком "
        f"(floor \u2192 ордер, після комісії {config.MRKT_FEE_PERCENT:.0f}%):\n"
    ]
    for name, buy_price, order_amount, profit in results[:top_n]:
        sign = "\U0001f7e2" if profit > 0 else "\u26aa"
        lines.append(
            f"{sign} {name}: floor {buy_price:.2f} \u2192 ордер {order_amount:.2f} TON, "
            f"прибуток {profit:+.2f} TON"
        )
    return "\n".join(lines)
