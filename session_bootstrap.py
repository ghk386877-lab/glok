"""
На Railway (і будь-де, де .session файлів ще немає на диску) відновлює їх
з Base64, збереженого у змінних середовища. Дозволяє деплоїти без ручного
завантаження файлів на сервер: закодував один раз локально, вставив у
Railway Variables, і бот сам розпаковує файл при кожному старті контейнера.

Локально (де файли вже лежать поруч зі скриптами) нічого не змінює - файл
вже існує, і функція просто нічого не робить.
"""
from __future__ import annotations

import base64
import logging
import os

import config

log = logging.getLogger(__name__)


def _restore(session_name: str, b64_env_var: str) -> None:
    path = f"{session_name}.session"
    if os.path.exists(path):
        return  # вже є локально - нічого робити не треба

    b64_value = os.getenv(b64_env_var, "")
    if not b64_value:
        return  # немає що відновлювати (нормально для локальної розробки)

    try:
        raw = base64.b64decode(b64_value)
        with open(path, "wb") as f:
            f.write(raw)
        log.info("Відновлено файл сесії '%s' зі змінної середовища %s.", path, b64_env_var)
    except Exception:
        log.exception("Не вдалось відновити файл сесії '%s' з %s", path, b64_env_var)


def restore_all() -> None:
    _restore(config.MRKT_SESSION_NAME, "MRKT_SESSION_B64")
    _restore(config.PORTALS_AUTH_SESSION_NAME, "PORTALS_AUTH_SESSION_B64")
