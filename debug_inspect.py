"""
Запусти цей скрипт ПЕРШИМ, перед стартом бота.

Друкує реальну структуру відповіді Portals (список, dict, чи кастомний
об'єкт бібліотеки на кшталт "Collections"/"PortalsGift"/"Activity"),
щоб звірити реальні назви полів з тим, що використовується у monitor.py.

Використання:
    python debug_inspect.py "tma your_auth_data_here"
"""
from __future__ import annotations

import asyncio
import json
import sys

import aportalsmp

_PRIMITIVES = (str, int, float, bool, type(None))


def _pretty(value) -> str:
    """Показує значення максимально інформативно, без 'проковтування' помилок."""
    if isinstance(value, _PRIMITIVES):
        return repr(value)
    if isinstance(value, (list, tuple)):
        header = f"[список, елементів: {len(value)}]"
        preview_items = []
        for v in value[:3]:
            preview_items.append(_pretty(v))
        preview = "\n".join(f"  елемент: {p}" for p in preview_items)
        return f"{header}\n{preview}"
    if isinstance(value, dict):
        try:
            return json.dumps(value, indent=2, ensure_ascii=False)
        except TypeError:
            return repr(value)
    # кастомний об'єкт бібліотеки - показуємо його реальні поля, а не repr()
    if hasattr(value, "__dict__"):
        inner = {k: _summarize(v) for k, v in vars(value).items()}
        return json.dumps(inner, indent=2, ensure_ascii=False, default=str)
    return repr(value)


def _summarize(value):
    """Компактне представлення для вкладених значень (щоб не плодити нескінченну вкладеність)."""
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, (list, tuple)):
        return [_summarize(v) for v in value[:3]] + (["..."] if len(value) > 3 else [])
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {k: _summarize(v) for k, v in vars(value).items()}
    return str(value)


def inspect_custom_object(label: str, obj) -> None:
    print(f"\n{'=' * 60}")
    print(f"== {label} ==")
    print(f"Python-тип: {type(obj)}")
    public_attrs = [a for a in dir(obj) if not a.startswith("_")]
    print(f"Публічні атрибути/методи (dir): {public_attrs}")

    if hasattr(obj, "__dict__"):
        print("\nРеальні поля екземпляра (з __dict__):")
        for k, v in vars(obj).items():
            print(f"\n  --- поле '{k}' (тип: {type(v)}) ---")
            print(_pretty(v))
    else:
        print("Об'єкт не має __dict__ - це, ймовірно, slots-based або builtin тип.")

    # окремо перевіряємо публічні атрибути/методи (напр. 'gift'), яких немає в __dict__
    for name in dir(obj):
        if name.startswith("_") or (hasattr(obj, "__dict__") and name in vars(obj)):
            continue
        try:
            attr = getattr(obj, name)
        except Exception as e:
            print(f"\n  '.{name}' -> помилка при доступі: {e}")
            continue
        print(f"\n  '.{name}' -> тип: {type(attr)}, callable: {callable(attr)}")
        if callable(attr):
            import inspect as _inspect
            try:
                print(f"    сигнатура: {_inspect.signature(attr)}")
            except (ValueError, TypeError):
                pass
            doc = getattr(attr, "__doc__", None)
            if doc:
                print(f"    docstring: {doc.strip()[:300]}")


def inspect_list(label: str, items: list) -> None:
    print(f"\n{'=' * 60}")
    print(f"== {label} ==")
    print(f"Це список, елементів: {len(items)}")
    for i, item in enumerate(items[:3]):
        print(f"\n--- елемент {i} (тип: {type(item)}) ---")
        if isinstance(item, _PRIMITIVES + (dict,)):
            print(_pretty(item))
        elif hasattr(item, "__dict__"):
            for k, v in vars(item).items():
                print(f"  {k} ({type(v).__name__}): {_summarize(v)}")
        else:
            print(f"dir(): {[a for a in dir(item) if not a.startswith('_')]}")


async def main() -> None:
    if len(sys.argv) < 2:
        print('Використання: python debug_inspect.py "tma <твій authData>"')
        sys.exit(1)

    auth = sys.argv[1]

    try:
        collections = await aportalsmp.collections(limit=10, authData=auth)
        inspect_custom_object("collections()", collections)
    except Exception as e:
        print(f"collections() кинув помилку: {type(e).__name__}: {e}")

    # marketActivity() поки пропускаємо: 401 "auth sign is invalid" - схоже, окрема
    # примха бібліотеки/ендпоінта, а collections() вже дає floor+обсяги торгів.
    # Розкоментуй, якщо захочеш перевірити ще раз:
    # try:
    #     activity = await aportalsmp.marketActivity(
    #         sort="latest", offset=0, limit=10, activityType="buy", authData=auth
    #     )
    #     inspect_list("marketActivity(activityType='buy')", activity)
    # except Exception as e:
    #     print(f"marketActivity() кинув помилку: {type(e).__name__}: {e}")

    try:
        results = await aportalsmp.search(sort="price_asc", limit=5, authData=auth)
        inspect_list("search(sort='price_asc', limit=5)", results)
    except Exception as e:
        print(f"search() кинув помилку: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
