"""
Звіти по арбітражу: порівняння floor-ціни Portals і MRKT для того самого
подарунка, з розрахунком реального прибутку в обидва боки, з урахуванням:
- комісій обох маркетплейсів (різна механіка нарахування, див. config.py)
- комісій за виведення подарунка з кожного маркетплейсу (потрібно, щоб
  перенести куплений подарунок на інший майданчик для продажу)

Назви колекцій мають збігатись дослівно між маркетплейсами (поки що
працюємо на припущенні, що спільні подарунки називаються однаково -
підтверджено для "Toy Bear").
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import config
import mrkt_client
import storage


@dataclass
class ArbitrageResult:
    buy_on: str
    buy_price: float          # скільки платиш за купівлю
    withdraw_fee: float       # комісія за виведення з майданчика купівлі
    sell_gross: float         # ціна, за якою продаєш (по флору іншого майданчика)
    sell_net: float           # скільки реально отримаєш після комісії продажу
    profit: float             # sell_net - buy_price - withdraw_fee


def _portals_seller_receives(listed_price: float) -> float:
    """Portals: продавець отримує listed_price мінус комісія маркетплейсу."""
    return listed_price * (1 - config.PORTALS_FEE_PERCENT / 100)


def _mrkt_buyer_pays(seller_wants: float) -> float:
    """MRKT: покупець платить seller_wants плюс комісія маркетплейсу зверху."""
    return seller_wants * (1 + config.MRKT_FEE_PERCENT / 100)


def compute_both_directions(portals_floor: float, mrkt_price: float, mrkt_price_without_fee: float):
    """
    mrkt_price - те, що заплатив би покупець на MRKT (з комісією) - це і є
        "флор" з точки зору покупця.
    mrkt_price_without_fee - те, що отримав би продавець на MRKT (без комісії).
    """
    # Напрям 1: купити на Portals (за floor), вивести з Portals, продати на MRKT
    buy1 = portals_floor
    withdraw1 = config.PORTALS_WITHDRAW_FEE_TON
    # щоб продати конкурентно на MRKT, орієнтуємось на поточний флор MRKT:
    # це те, що заплатить покупець; ми, як продавець, отримаємо цю суму
    # МІНУС комісію MRKT (бо на MRKT комісію платить покупець зверху, тобто
    # якщо ми хочемо, щоб покупець заплатив mrkt_price, ми отримаємо
    # mrkt_price / (1 + fee%))
    sell1_gross = mrkt_price
    sell1_net = mrkt_price / (1 + config.MRKT_FEE_PERCENT / 100)
    profit1 = sell1_net - buy1 - withdraw1

    dir1 = ArbitrageResult(
        buy_on="Portals", buy_price=buy1, withdraw_fee=withdraw1,
        sell_gross=sell1_gross, sell_net=sell1_net, profit=profit1,
    )

    # Напрям 2: купити на MRKT (за floor, тобто заплатити mrkt_price з комісією),
    # вивести з MRKT, продати на Portals за floor_price Portals (продавець
    # отримує floor_price мінус комісія Portals)
    buy2 = mrkt_price
    withdraw2 = config.MRKT_WITHDRAW_FEE_TON
    sell2_gross = portals_floor
    sell2_net = _portals_seller_receives(portals_floor)
    profit2 = sell2_net - buy2 - withdraw2

    dir2 = ArbitrageResult(
        buy_on="MRKT", buy_price=buy2, withdraw_fee=withdraw2,
        sell_gross=sell2_gross, sell_net=sell2_net, profit=profit2,
    )

    return dir1, dir2


def _fmt_direction(d: ArbitrageResult, sell_on: str) -> str:
    sign = "\U0001f7e2" if d.profit > 0 else "\U0001f534"
    return (
        f"{sign} Купити на {d.buy_on} ({d.buy_price:.2f} TON) \u2192 вивести "
        f"({d.withdraw_fee:.2f} TON) \u2192 продати на {sell_on} "
        f"(отримаєш {d.sell_net:.2f} TON)\n"
        f"   Прибуток: {d.profit:+.2f} TON"
    )


async def build_arbitrage_report(gift_name: str) -> str:
    portals_latest = await storage.get_latest(gift_name)
    if not portals_latest:
        return (
            f"Не знайшов '{gift_name}' у даних Portals. Перевір назву "
            f"(така, як у /floors)."
        )
    portals_floor = portals_latest["floor_price"]

    try:
        mrkt_offer = await mrkt_client.get_floor(gift_name)
    except mrkt_client.MrktError as e:
        return f"Помилка MRKT: {e}"

    lines = [f"\u2696\ufe0f Арбітраж '{gift_name}':\n", f"Portals floor: {portals_floor:.2f} TON"]

    if mrkt_offer is None:
        lines.append("MRKT: активних лістингів немає - розрахунок прибутку неможливий.")
        return "\n".join(lines)

    mrkt_price = mrkt_offer["price"]
    mrkt_price_no_fee = mrkt_offer["price_without_fee"]
    lines.append(f"MRKT floor (з комісією, платить покупець): {mrkt_price:.2f} TON\n")

    dir1, dir2 = compute_both_directions(portals_floor, mrkt_price, mrkt_price_no_fee)
    lines.append(_fmt_direction(dir1, "MRKT"))
    lines.append("")
    lines.append(_fmt_direction(dir2, "Portals"))

    best = dir1 if dir1.profit > dir2.profit else dir2
    if best.profit > 0:
        lines.append(f"\n\U0001f4b0 Вигідніше: купити на {best.buy_on} (прибуток {best.profit:+.2f} TON)")
    else:
        lines.append("\n\u26a0\ufe0f Наразі жоден напрям не прибутковий після комісій і виведення.")

    return "\n".join(lines)


async def _fetch_arbitrage_row(sem: asyncio.Semaphore, name: str):
    async with sem:
        portals_latest = await storage.get_latest(name)
        if not portals_latest:
            return None
        portals_floor = portals_latest["floor_price"]

        try:
            mrkt_offer = await mrkt_client.get_floor(name)
        except mrkt_client.MrktError:
            return None
        if mrkt_offer is None:
            return ("no_listing", name, portals_floor, None, None)

        mrkt_price = mrkt_offer["price"]
        mrkt_price_no_fee = mrkt_offer["price_without_fee"]
        dir1, dir2 = compute_both_directions(portals_floor, mrkt_price, mrkt_price_no_fee)
        best = dir1 if dir1.profit > dir2.profit else dir2
        return ("ok", name, portals_floor, mrkt_price, best)


async def build_top_arbitrage_report(gift_names: list[str], top_n: int | None = None) -> str:
    """Арбітраж по кількох подарунках одразу - запити паралельні (обмежені
    config.API_CONCURRENCY_LIMIT), результат сортується за прибутком."""
    top_n = top_n or config.TOP_N_DISPLAY
    sem = asyncio.Semaphore(config.API_CONCURRENCY_LIMIT)
    raw = await asyncio.gather(*(_fetch_arbitrage_row(sem, name) for name in gift_names))

    ok_rows = [r for r in raw if r and r[0] == "ok"]
    ok_rows.sort(key=lambda r: r[4].profit, reverse=True)

    lines = ["\u2696\ufe0f Арбітраж Portals vs MRKT (кращий напрям по кожному):\n"]
    for _, name, portals_floor, mrkt_price, best in ok_rows[:top_n]:
        sign = "\U0001f7e2" if best.profit > 0 else "\u26aa"
        lines.append(
            f"{sign} {name}: Portals {portals_floor:.2f} / MRKT {mrkt_price:.2f} TON \u2192 "
            f"купити на {best.buy_on}, прибуток {best.profit:+.2f} TON"
        )

    if not ok_rows:
        lines.append("Дані відсутні (немає активних лістингів на MRKT для перевірених подарунків).")

    return "\n".join(lines)
