"""
Шукає внутрішній токен/сесію в підключеному amrkt.MarketClient - щоб
зробити прямий запит до /api/v1/orders (публічної функції для цього в
бібліотеці немає, але сама бібліотека десь тримає токен, яким підписує
свої ж запити - спробуємо його перевикористати).

Використання:
    python inspect_mrkt_internals.py
"""
import asyncio
import inspect
import os

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("MRKT_API_ID")
API_HASH = os.getenv("MRKT_API_HASH")
SESSION_NAME = os.getenv("MRKT_SESSION_NAME", "mrkt_session")


async def main() -> None:
    from amrkt import MarketClient

    client = MarketClient(api_id=int(API_ID), api_hash=API_HASH, session_name=SESSION_NAME)

    async with client:
        print("=" * 60)
        print("Атрибути екземпляра client (dir + __dict__):\n")
        for attr in dir(client):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(client, attr)
            except Exception as e:
                print(f"  {attr}: помилка доступу ({e})")
                continue
            if callable(value):
                continue
            print(f"  {attr} ({type(value).__name__}): {str(value)[:200]}")

        print("\nПриватні атрибути (можуть містити token/session/headers):")
        for attr in vars(client):
            if any(k in attr.lower() for k in ("token", "auth", "session", "header", "http", "client")):
                value = getattr(client, attr)
                print(f"  {attr} ({type(value).__name__}): {str(value)[:300]}")

        print("\n" + "=" * 60)
        print("Сигнатура search_gifts (для порівняння, чи є десь схожий метод get_orders):")
        for name in dir(client):
            if "order" in name.lower() and not name.startswith("_"):
                fn = getattr(client, name)
                try:
                    print(f"  {name}{inspect.signature(fn)}")
                except (TypeError, ValueError):
                    print(f"  {name} (сигнатура недоступна)")


if __name__ == "__main__":
    asyncio.run(main())
