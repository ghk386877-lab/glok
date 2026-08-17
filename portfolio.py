"""
Трекер портфеля: власні угоди користувача (купив/продав), реалізований і
нереалізований прибуток. Ціни вводить сам користувач (реальні суми угод,
які він фактично заплатив/отримав) - тому для РЕАЛІЗОВАНИХ угод комісії
окремо не рахуються, вони вже "всередині" введених цін.

Для НЕРЕАЛІЗОВАНИХ (відкритих) позицій оцінка ведеться від floor-ціни на
Portals, з припущенням, що продаж теж буде на Portals - тому floor тут
зменшується на комісію Portals (config.PORTALS_FEE_PERCENT), інакше оцінка
була б завищена відносно того, скільки реально отримаєш при продажу.
"""
from __future__ import annotations

import time

import config
import storage


def _net_sell_value(floor_price: float) -> float:
    """Скільки реально отримаєш, продавши по floor на Portals (мінус комісія)."""
    return floor_price * (1 - config.PORTALS_FEE_PERCENT / 100)


def _date_str(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


async def build_portfolio_report(chat_id: int) -> str:
    open_positions = await storage.get_open_positions(chat_id)
    closed_trades = await storage.get_closed_trades(chat_id)

    if not open_positions and not closed_trades:
        return (
            "\U0001f4bc Портфель порожній.\n\n"
            "Додай купівлю: /buy <назва> <ціна>, напр. /buy Toy Bear 32.5\n"
            "Закрий продажем: /sell <назва> <ціна>"
        )

    lines = ["\U0001f4bc Портфель:\n"]

    realized_total = sum(t["profit"] for t in closed_trades)
    lines.append(
        f"\U0001f4b0 Реалізований прибуток ({len(closed_trades)} закритих угод): "
        f"{realized_total:+.2f} TON\n"
    )

    if open_positions:
        lines.append(
            f"\U0001f4e6 Відкриті позиції (оцінка продажу по floor Portals, "
            f"мінус комісія {config.PORTALS_FEE_PERCENT:.0f}%):"
        )
        unrealized_total = 0.0
        have_current = False
        for pos in open_positions:
            latest = await storage.get_latest(pos["gift_name"])
            current = latest["floor_price"] if latest else None
            if current is not None:
                net_value = _net_sell_value(current)
                unrealized = net_value - pos["buy_price"]
                unrealized_total += unrealized
                have_current = True
                sign = "\U0001f7e2" if unrealized > 0 else "\U0001f534"
                lines.append(
                    f"{sign} #{pos['id']} {pos['gift_name']}: купив за {pos['buy_price']:.2f}, "
                    f"floor {current:.2f} (чисто {net_value:.2f}) \u2192 {unrealized:+.2f} TON"
                )
            else:
                lines.append(
                    f"\u26aa #{pos['id']} {pos['gift_name']}: купив за {pos['buy_price']:.2f} "
                    f"(даних по floor ще немає)"
                )
        if have_current:
            lines.append(f"\nНереалізований прибуток: {unrealized_total:+.2f} TON")
    else:
        lines.append("Відкритих позицій немає.")

    if closed_trades:
        lines.append("\n\U0001f4c5 Закриті угоди по датах:")
        groups: dict[str, list[dict]] = {}
        for t in closed_trades:
            day = _date_str(t["sell_ts"])
            groups.setdefault(day, []).append(t)
        for day in sorted(groups.keys(), reverse=True):
            day_trades = groups[day]
            day_profit = sum(t["profit"] for t in day_trades)
            sign = "\U0001f7e2" if day_profit > 0 else "\U0001f534"
            lines.append(f"\n{sign} {day}: {day_profit:+.2f} TON ({len(day_trades)} угод)")
            for t in day_trades:
                lines.append(
                    f"   \u2022 {t['gift_name']}: {t['buy_price']:.2f} \u2192 "
                    f"{t['sell_price']:.2f} ({t['profit']:+.2f} TON)"
                )

    lines.append(
        "\n\u2139\ufe0f /sell закриває найстарішу відкриту позицію з такою назвою (FIFO). "
        "/delete_trade <id> - видалити помилково введену угоду."
    )
    return "\n".join(lines)
