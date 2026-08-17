"""
Точка входу. Піднімає:
1) APScheduler job, який регулярно тягне дані з Portals і зберігає знімки;
2) Telegram-бота, який показує звіти по цих знімках.

Запуск:
    pip install -r requirements.txt
    cp .env.example .env   # і заповнити BOT_TOKEN, ADMIN_IDS, (опційно) PORTALS_AUTH_DATA
    python main.py
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, CommandHandler

import auth_store
import bot as bot_handlers
import config
import monitor
import portals_auth
import session_bootstrap
import storage
import webapp_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


async def scheduled_auth_refresh() -> None:
    await portals_auth.refresh()


async def scheduled_poll(application: Application) -> None:
    if not auth_store.get_auth():
        log.warning("authData не задано - пропускаю опитування. Встанови /setauth в боті.")
        return
    try:
        saved, alerts = await monitor.poll_once()
        log.info("Опитування виконано, збережено знімків: %s, алертів: %s", saved, len(alerts))
        if alerts:
            await _notify_subscribers(application, alerts)
    except Exception:
        log.exception("Помилка під час опитування Portals")

    # прибираємо знімки старші за 3 дні, щоб база не росла нескінченно
    await storage.prune_older_than(3 * 24 * 60 * 60)


async def _notify_subscribers(application: Application, alerts: list[dict]) -> None:
    chat_ids = await storage.get_subscriptions()
    if not chat_ids:
        return

    lines = ["\u26a1 Різка зміна floor-ціни:\n"]
    for a in alerts:
        arrow = "\U0001f7e2\u2b06" if a["pct"] > 0 else "\U0001f534\u2b07"
        lines.append(
            f"{arrow} {a['name']}: {a['old_price']:.2f} \u2192 {a['new_price']:.2f} TON "
            f"({a['pct']:+.1f}%)"
        )
    text = "\n".join(lines)

    for chat_id in chat_ids:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            log.exception("Не вдалось надіслати алерт у chat_id=%s", chat_id)


async def run() -> None:
    session_bootstrap.restore_all()
    await storage.init_db()

    import mrkt_client
    await mrkt_client.connect()

    if portals_auth.is_configured():
        log.info("Оновлюю authData Portals автоматично перед стартом...")
        await portals_auth.refresh()
    else:
        log.info(
            "Автооновлення Portals authData не налаштовано (MRKT_API_ID/HASH відсутні) "
            "- використовуй /setauth вручну."
        )

    application = Application.builder().token(config.BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", bot_handlers.cmd_start))
    application.add_handler(CommandHandler("app", bot_handlers.cmd_app))
    application.add_handler(CommandHandler("help", bot_handlers.cmd_help))
    application.add_handler(CommandHandler("floors", bot_handlers.cmd_floors))
    application.add_handler(CommandHandler("volume", bot_handlers.cmd_volume))
    application.add_handler(CommandHandler("range", bot_handlers.cmd_range))
    application.add_handler(CommandHandler("orders", bot_handlers.cmd_orders))
    application.add_handler(CommandHandler("orders_top", bot_handlers.cmd_orders_top))
    application.add_handler(CommandHandler("arbitrage", bot_handlers.cmd_arbitrage))
    application.add_handler(CommandHandler("arbitrage_top", bot_handlers.cmd_arbitrage_top))
    application.add_handler(CommandHandler("subscribe", bot_handlers.cmd_subscribe))
    application.add_handler(CommandHandler("unsubscribe", bot_handlers.cmd_unsubscribe))
    application.add_handler(CommandHandler("setauth", bot_handlers.cmd_setauth))
    application.add_handler(CommandHandler("refreshauth", bot_handlers.cmd_refreshauth))
    application.add_handler(CommandHandler("poll", bot_handlers.cmd_poll))
    application.add_handler(CommandHandler("status", bot_handlers.cmd_status))

    scheduler = AsyncIOScheduler()
    # next_run_time=now -> перше опитування відбувається одразу при старті,
    # а не через POLL_INTERVAL_SECONDS (інакше боту нема чим відповідати
    # на /floors в перші кілька хвилин після запуску).
    from datetime import datetime

    scheduler.add_job(
        scheduled_poll,
        "interval",
        seconds=config.POLL_INTERVAL_SECONDS,
        next_run_time=datetime.now(),
        args=[application],
    )
    if portals_auth.is_configured():
        scheduler.add_job(
            scheduled_auth_refresh,
            "interval",
            seconds=config.PORTALS_AUTH_REFRESH_INTERVAL_SECONDS,
        )
    scheduler.start()

    async with application:
        await application.start()
        await application.updater.start_polling()
        await webapp_server.run_webapp_server(config.WEBAPP_PORT)
        log.info("Бот запущений. Очікую команди...")
        try:
            # тримаємо процес живим
            await asyncio.Event().wait()
        finally:
            await mrkt_client.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
