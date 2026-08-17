"""
Перевіряє РЕАЛЬНУ структуру даних amrkt (MRKT), перш ніж прив'язувати до неї
логіку арбітражу - той самий підхід, що і з aportalsmp/tonnelmp: без здогадок.

Запускати ПІСЛЯ setup_mrkt.py (файл сесії має вже існувати).

Використання:
    python inspect_mrkt.py "Toy Bear"
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("MRKT_API_ID")
API_HASH = os.getenv("MRKT_API_HASH")
SESSION_NAME = os.getenv("MRKT_SESSION_NAME", "mrkt_session")

_PRIMITIVES = (str, int, float, bool, type(None))


def _summarize(value, depth: int = 0):
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, (list, tuple)):
        return [_summarize(v, depth + 1) for v in value[:3]] + (
            ["..."] if len(value) > 3 else []
        )
    if isinstance(value, dict):
        return {k: _summarize(v, depth + 1) for k, v in value.items()}
    if hasattr(value, "__dict__"):
        return {k: _summarize(v, depth + 1) for k, v in vars(value).items()}
    if hasattr(value, "model_dump"):  # pydantic model
        return _summarize(value.model_dump(), depth + 1)
    return str(value)


async def main() -> None:
    if not API_ID or not API_HASH:
        print("Спочатку задай MRKT_API_ID і MRKT_API_HASH у .env, і запусти setup_mrkt.py")
        return

    gift_name = sys.argv[1] if len(sys.argv) > 1 else "Toy Bear"

    from amrkt import MarketClient

    client = MarketClient(api_id=int(API_ID), api_hash=API_HASH, session_name=SESSION_NAME)

    async with client:
        print("=" * 60)
        print("Сигнатура search_gifts():")
        try:
            print(inspect.signature(client.search_gifts))
        except (TypeError, ValueError) as e:
            print(f"Не вдалось отримати сигнатуру: {e}")

        print("\n" + "=" * 60)
        print(f"== search_gifts(collection_names=['{gift_name}'], count=5) ==")
        try:
            result = await client.search_gifts(collection_names=[gift_name], count=5)
            print(f"Тип результату: {type(result)}")
            print(json.dumps(_summarize(result), indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"Помилка: {type(e).__name__}: {e}")

        print("\n" + "=" * 60)
        print("== get_user_info() / get_balance() (перевірка з'єднання) ==")
        try:
            user = await client.get_user_info()
            balance = await client.get_balance()
            print(f"Користувач: {_summarize(user)}")
            print(f"Баланс: {_summarize(balance)}")
        except Exception as e:
            print(f"Помилка: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
