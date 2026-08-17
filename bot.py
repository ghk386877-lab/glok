"""
Обробники команд Telegram-бота.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

import auth_store
import config
import reports
import storage

log = logging.getLogger(__name__)

HELP_TEXT = (
    "Команди:\n"
    "/app - відкрити Mini App (Огляд / Арбітраж / Ордери)\n"
    "/floors - усі подарунки: floor-ціна і зміна за 24 год\n"
    "/volume - топ подарунків за об'ємом торгів за 24 год\n"
    "/range 0-3 | 3-10 | 10-20 - подарунки у ціновому діапазоні (TON)\n"
    "/orders <назва> - різниця floor-ціни і найкращого офера на купівлю (напр. /orders Vice Cream)\n"
    "/orders_top - топ-10 за можливим прибутком (офер\u2192floor), тільки ліквідні (\u226510 продажів/24г)\n"
    "/arbitrage <назва> - порівняння floor-ціни Portals vs MRKT (напр. /arbitrage Toy Bear)\n"
    "/arbitrage_top - те саме для топ-10 подарунків за об'ємом торгів\n"
    "/subscribe - отримувати сповіщення про різку зміну floor-ціни (\u2265"
    f" {config.ALERT_THRESHOLD_PERCENT:.0f}%)\n"
    "/unsubscribe - вимкнути ці сповіщення\n"
    "/setauth <tma ...> - оновити authData Portals (тільки для адміну)\n"
    "/refreshauth - примусово оновити authData Portals автоматично (тільки для адміну)\n"
    "/poll - примусово оновити дані просто зараз (тільки для адміну)\n"
    "/status - перевірити, чи заданий authData і коли останнє опитування\n"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привіт! Я бот-монітор подарунків Portals.\n\n" + HELP_TEXT)


async def cmd_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.WEBAPP_URL:
        await update.message.reply_text(
            "Mini App URL не задано. Онови WEBAPP_URL в .env (публічний Railway "
            "домен, Settings -> Networking -> Generate Domain), потім перезапусти бота."
        )
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("\U0001f4f1 Відкрити Mini App", web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    )
    await update.message.reply_text("Тисни, щоб відкрити:", reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def cmd_floors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await reports.build_floors_report()
    await update.message.reply_text(text)


async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await reports.build_volume_report()
    await update.message.reply_text(text)


async def cmd_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        available = ", ".join(config.PRICE_RANGES.keys())
        await update.message.reply_text(f"Вкажи діапазон, наприклад: /range 0-3\nДоступні: {available}")
        return
    text = await reports.build_range_report(context.args[0])
    await update.message.reply_text(text)


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import orders

    if not context.args:
        await update.message.reply_text(
            "Вкажи назву подарунка, наприклад: /orders Vice Cream"
        )
        return
    gift_name = " ".join(context.args)
    await update.message.reply_text(f"Дивлюсь офери для '{gift_name}'...")
    try:
        text = await orders.build_order_report(gift_name)
    except Exception as e:
        text = f"Помилка: {type(e).__name__}: {e}"
    await update.message.reply_text(text)


async def cmd_orders_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import orders

    names = await storage.get_all_latest_gift_names()
    if not names:
        await update.message.reply_text("Ще немає даних - зачекай перше опитування.")
        return

    valid_names = []
    for name in names:
        latest = await storage.get_latest(name)
        if latest and (latest["sales_24h_count"] or 0) >= config.MIN_SALES_24H_FOR_VALID:
            valid_names.append((name, latest["volume_24h"] or 0))

    if not valid_names:
        await update.message.reply_text(
            f"Немає подарунків з \u2265{config.MIN_SALES_24H_FOR_VALID} продажів за 24г."
        )
        return

    # запобіжник: якщо валідних забагато, беремо перші N за обсягом торгів,
    # щоб не перевантажувати API занадто великою кількістю запитів
    valid_names.sort(key=lambda r: r[1], reverse=True)
    candidate_names = [name for name, _ in valid_names[: config.ORDERS_CANDIDATE_POOL]]

    await update.message.reply_text(
        f"Перевіряю офери для {len(candidate_names)} ліквідних подарунків "
        f"(\u2265{config.MIN_SALES_24H_FOR_VALID} продажів/24г), зачекай..."
    )
    try:
        text = await orders.build_profit_ranked_report(candidate_names, top_n=config.TOP_N_DISPLAY)
    except Exception as e:
        text = f"Помилка: {type(e).__name__}: {e}"
    await update.message.reply_text(text)


async def cmd_arbitrage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import arbitrage
    import mrkt_client

    if not mrkt_client.is_connected():
        await update.message.reply_text(
            "MRKT не підключено. Перевір MRKT_API_ID/MRKT_API_HASH в .env і "
            "чи виконаний setup_mrkt.py, потім перезапусти бота."
        )
        return
    if not context.args:
        await update.message.reply_text(
            "Вкажи назву подарунка, наприклад: /arbitrage Toy Bear"
        )
        return
    gift_name = " ".join(context.args)
    await update.message.reply_text(f"Порівнюю ціни для '{gift_name}'...")
    try:
        text = await arbitrage.build_arbitrage_report(gift_name)
    except Exception as e:
        text = f"Помилка: {type(e).__name__}: {e}"
    await update.message.reply_text(text)


async def cmd_arbitrage_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import arbitrage
    import mrkt_client

    if not mrkt_client.is_connected():
        await update.message.reply_text(
            "MRKT не підключено. Перевір MRKT_API_ID/MRKT_API_HASH в .env і "
            "чи виконаний setup_mrkt.py, потім перезапусти бота."
        )
        return

    names = await storage.get_all_latest_gift_names()
    rows = []
    for name in names:
        latest = await storage.get_latest(name)
        if latest and latest["volume_24h"] is not None:
            rows.append((name, latest["volume_24h"]))
    rows.sort(key=lambda r: r[1], reverse=True)
    top_names = [name for name, _ in rows[: config.ARBITRAGE_CANDIDATE_POOL]]

    if not top_names:
        await update.message.reply_text("Даних про об'єм торгів поки немає.")
        return

    await update.message.reply_text(
        f"Порівнюю ціни для топ-{len(top_names)} подарунків, зачекай..."
    )
    try:
        text = await arbitrage.build_top_arbitrage_report(top_names)
    except Exception as e:
        text = f"Помилка: {type(e).__name__}: {e}"
    await update.message.reply_text(text)


async def cmd_setauth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if config.ADMIN_IDS and user_id not in config.ADMIN_IDS:
        await update.message.reply_text("Ця команда доступна тільки адміну.")
        return
    if not context.args:
        await update.message.reply_text("Використання: /setauth tma <твій довгий токен>")
        return
    new_auth = update.message.text.split(maxsplit=1)[1].strip()
    auth_store.set_auth(new_auth)
    await update.message.reply_text("authData оновлено.")


async def cmd_refreshauth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import portals_auth

    user_id = update.effective_user.id if update.effective_user else None
    if config.ADMIN_IDS and user_id not in config.ADMIN_IDS:
        await update.message.reply_text("Ця команда доступна тільки адміну.")
        return
    if not portals_auth.is_configured():
        await update.message.reply_text(
            "Автооновлення не налаштовано: задай MRKT_API_ID/MRKT_API_HASH в .env "
            "і виконай setup_portals_auth.py."
        )
        return
    await update.message.reply_text("Оновлюю authData через Pyrogram-сесію...")
    new_auth = await portals_auth.refresh()
    if new_auth:
        await update.message.reply_text(f"Готово! authData оновлено (перші 40 символів): {new_auth[:40]}...")
    else:
        await update.message.reply_text(
            "Не вдалось оновити автоматично. Перевір, чи виконаний "
            "setup_portals_auth.py, або онови вручну через /setauth."
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    auth_set = "так" if auth_store.get_auth() else "ні (задай через /setauth)"
    await update.message.reply_text(
        f"authData заданий: {auth_set}\n"
        f"Інтервал опитування: {config.POLL_INTERVAL_SECONDS} сек"
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await storage.add_subscription(chat_id)
    await update.message.reply_text(
        f"Готово! Сповіщу тебе тут, якщо floor-ціна якогось подарунка "
        f"зміниться за один цикл опитування на \u2265{config.ALERT_THRESHOLD_PERCENT:.0f}%."
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await storage.remove_subscription(chat_id)
    await update.message.reply_text("Сповіщення про різку зміну ціни вимкнено.")


async def cmd_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ручний тригер опитування Portals - зручно для перевірки, не чекаючи інтервал."""
    import monitor

    user_id = update.effective_user.id if update.effective_user else None
    if config.ADMIN_IDS and user_id not in config.ADMIN_IDS:
        await update.message.reply_text("Ця команда доступна тільки адміну.")
        return
    if not auth_store.get_auth():
        await update.message.reply_text("Спочатку задай authData через /setauth.")
        return
    await update.message.reply_text("Опитую Portals, зачекай кілька секунд...")
    try:
        saved, alerts = await monitor.poll_once()
        text = f"Готово, збережено знімків: {saved}"
        if alerts:
            text += f"\nЗнайдено різких змін ціни: {len(alerts)} (сповіщення підуть підписникам)."
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Помилка під час опитування: {type(e).__name__}: {e}")
