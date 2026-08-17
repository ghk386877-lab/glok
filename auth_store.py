"""
authData у Portals живе недовго (за спостереженнями спільноти - від 1 до 7 днів),
тому тримаємо його в пам'яті процесу і даємо змогу оновити "на льоту"
через команду /setauth, без перезапуску бота.
"""
import config

_current_auth = config.PORTALS_AUTH_DATA


def get_auth() -> str:
    return _current_auth


def set_auth(value: str) -> None:
    global _current_auth
    _current_auth = value.strip()
