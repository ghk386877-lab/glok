"""
Періодичний job: тягне поточні дані по всіх колекціях подарунків з Portals
і зберігає знімок floor-ціни/об'єму в SQLite.

Назви полів нижче підтверджені реальним викликом collections() через
debug_inspect.py 09.07.2026 - "name", "floor_price", "day_volume", "sales_24h_count".
"""
from __future__ import annotations

import logging
from typing import Any

import config
import portals_client
import storage

log = logging.getLogger(__name__)

_NAME_KEYS = ("name",)
_FLOOR_KEYS = ("floor_price",)
_VOLUME_KEYS = ("day_volume",)
_SALES_COUNT_KEYS = ("sales_24h_count",)
_ID_KEYS = ("id",)


def _first_present(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def poll_once() -> tuple[int, list[dict[str, Any]]]:
    """
    Один прохід опитування.
    Повертає (кількість збережених знімків, список алертів про різку зміну ціни).
    Алерт спрацьовує, якщо floor-ціна змінилась відносно попереднього знімка
    більше ніж на config.ALERT_THRESHOLD_PERCENT відсотків.
    """
    collections = await portals_client.get_collections()
    saved = 0
    alerts: list[dict[str, Any]] = []

    for item in collections:
        name = _first_present(item, _NAME_KEYS)
        floor = _to_float(_first_present(item, _FLOOR_KEYS))
        volume = _to_float(_first_present(item, _VOLUME_KEYS))
        sales_count = _to_int(_first_present(item, _SALES_COUNT_KEYS))
        collection_id = _first_present(item, _ID_KEYS)
        if name is None or floor is None:
            log.warning("Пропускаю запис з незрозумілою структурою: %s", item)
            continue

        if collection_id:
            await storage.save_collection_id(name, collection_id)

        previous = await storage.get_latest(name)
        if previous and previous["floor_price"]:
            prev_floor = previous["floor_price"]
            pct = (floor - prev_floor) / prev_floor * 100
            if abs(pct) >= config.ALERT_THRESHOLD_PERCENT:
                alerts.append(
                    {
                        "name": name,
                        "old_price": prev_floor,
                        "new_price": floor,
                        "pct": pct,
                    }
                )

        await storage.save_snapshot(name, floor, volume, sales_count)
        saved += 1

    return saved, alerts
