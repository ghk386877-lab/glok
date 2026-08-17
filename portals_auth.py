"""
Автоматичне оновлення authData Portals через aportalsmp.update_auth(),
використовуючи окрему Pyrogram-сесію (створену setup_portals_auth.py).

Після цього /setauth стає запасним варіантом "на всякий випадок", а не
обов'язковою щоденною дією.
"""
from __future__ import annotations

import logging

import auth_store
import config

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(config.MRKT_API_ID and config.MRKT_API_HASH)


async def refresh() -> str | None:
    """
    Оновлює authData Portals і одразу зберігає його в auth_store.
    Повертає новий authData, або None якщо не вдалось (наприклад, сесія
    ще не створена - треба спершу запустити setup_portals_auth.py).
    """
    if not is_configured():
        log.warning(
            "MRKT_API_ID/MRKT_API_HASH не задані - автооновлення Portals authData "
            "вимкнено. /setauth лишається єдиним способом."
        )
        return None

    import aportalsmp

    try:
        new_auth = await aportalsmp.update_auth(
            api_id=int(config.MRKT_API_ID),
            api_hash=config.MRKT_API_HASH,
            session_name=config.PORTALS_AUTH_SESSION_NAME,
        )
    except Exception:
        log.exception(
            "Не вдалось автоматично оновити authData Portals. Перевір, чи "
            "виконаний setup_portals_auth.py. Можна оновити вручну через /setauth."
        )
        return None

    auth_store.set_auth(new_auth)
    log.info("authData Portals оновлено автоматично.")
    return new_auth
