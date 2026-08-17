"""
Легкий веб-сервер (aiohttp) для Mini App: віддає index.html і JSON API.
Працює в тому самому процесі й asyncio event loop, що й сам бот - окремий
Railway-сервіс не потрібен.
"""
from __future__ import annotations

import json
import logging
import os

from aiohttp import web

import storage
import webapp_api
import price_feed

log = logging.getLogger(__name__)

_BASE_DIR = os.path.join(os.path.dirname(__file__), "webapp")
_STATIC_DIR = os.path.join(_BASE_DIR, "static")


def _json_response(data) -> web.Response:
    return web.Response(
        text=json.dumps(data, ensure_ascii=False), content_type="application/json"
    )


async def handle_index(request: web.Request) -> web.Response:
    path = os.path.join(_BASE_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html")


async def handle_floors(request: web.Request) -> web.Response:
    return _json_response(await webapp_api.get_floors())


async def handle_volume(request: web.Request) -> web.Response:
    return _json_response(await webapp_api.get_volume())


async def handle_range(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    return _json_response(await webapp_api.get_range(key))


async def handle_orders_top(request: web.Request) -> web.Response:
    try:
        data = await webapp_api.get_orders_top()
        return _json_response(data)
    except Exception:
        log.exception("Помилка /api/orders_top")
        return _json_response([])


async def handle_arbitrage_top(request: web.Request) -> web.Response:
    try:
        data = await webapp_api.get_arbitrage_top()
        return _json_response(data)
    except Exception:
        log.exception("Помилка /api/arbitrage_top")
        return _json_response([])


async def handle_price(request: web.Request) -> web.Response:
    price = await price_feed.get_ton_usd_price()
    return _json_response({"usd": price})


async def handle_gift_names(request: web.Request) -> web.Response:
    return _json_response(await webapp_api.get_gift_names())


async def handle_portfolio_get(request: web.Request) -> web.Response:
    try:
        chat_id = int(request.query.get("chat_id", "0"))
    except ValueError:
        return web.Response(status=400, text="invalid chat_id")
    if not chat_id:
        return web.Response(status=400, text="chat_id required")
    data = await webapp_api.get_portfolio(chat_id)
    return _json_response(data)


async def handle_portfolio_buy(request: web.Request) -> web.Response:
    body = await request.json()
    chat_id = int(body.get("chat_id", 0))
    gift_name = (body.get("gift_name") or "").strip()
    price = float(body.get("price", 0))
    if not chat_id or not gift_name or price <= 0:
        return web.Response(status=400, text="chat_id, gift_name, price required")
    trade_id = await storage.add_purchase(chat_id, gift_name, price)
    return _json_response({"id": trade_id})


async def handle_portfolio_sell(request: web.Request) -> web.Response:
    body = await request.json()
    chat_id = int(body.get("chat_id", 0))
    gift_name = (body.get("gift_name") or "").strip()
    price = float(body.get("price", 0))
    if not chat_id or not gift_name or price <= 0:
        return web.Response(status=400, text="chat_id, gift_name, price required")
    result = await storage.close_oldest_open(chat_id, gift_name, price)
    if not result:
        return web.Response(status=404, text="no open position found")
    return _json_response(result)


async def handle_portfolio_delete(request: web.Request) -> web.Response:
    body = await request.json()
    chat_id = int(body.get("chat_id", 0))
    trade_id = int(body.get("trade_id", 0))
    if not chat_id or not trade_id:
        return web.Response(status=400, text="chat_id, trade_id required")
    ok = await storage.delete_trade(chat_id, trade_id)
    return _json_response({"deleted": ok})


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/floors", handle_floors)
    app.router.add_get("/api/volume", handle_volume)
    app.router.add_get("/api/range/{key}", handle_range)
    app.router.add_get("/api/orders_top", handle_orders_top)
    app.router.add_get("/api/arbitrage_top", handle_arbitrage_top)
    app.router.add_get("/api/price", handle_price)
    app.router.add_get("/api/gift_names", handle_gift_names)
    app.router.add_get("/api/portfolio", handle_portfolio_get)
    app.router.add_post("/api/portfolio/buy", handle_portfolio_buy)
    app.router.add_post("/api/portfolio/sell", handle_portfolio_sell)
    app.router.add_post("/api/portfolio/delete", handle_portfolio_delete)
    if os.path.isdir(_STATIC_DIR):
        app.router.add_static("/static", _STATIC_DIR, name="static")
    return app


async def run_webapp_server(port: int) -> None:
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("Mini App веб-сервер запущено на порту %s", port)
