"""
Шукає всі методи MarketClient, пов'язані з оферами/бідами (купівля нижче
floor), через інтроспекцію - перш ніж вирішувати, чи є на MRKT щось
аналогічне topOffer() з Portals.

Використання:
    python inspect_mrkt_offers.py
"""
import inspect
import os

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("MRKT_API_ID")
API_HASH = os.getenv("MRKT_API_HASH")
SESSION_NAME = os.getenv("MRKT_SESSION_NAME", "mrkt_session")


def main() -> None:
    from amrkt import MarketClient

    client = MarketClient(api_id=int(API_ID), api_hash=API_HASH, session_name=SESSION_NAME)

    print("=" * 60)
    print("Усі публічні методи MarketClient:")
    all_methods = [
        m for m in dir(client)
        if not m.startswith("_") and callable(getattr(client, m))
    ]
    for m in all_methods:
        print(f"  {m}")

    print("\n" + "=" * 60)
    print("Методи, що містять 'offer' або 'bid' у назві:")
    offer_methods = [m for m in all_methods if "offer" in m.lower() or "bid" in m.lower()]
    if not offer_methods:
        print("  Жодного не знайдено.")
    for m in offer_methods:
        fn = getattr(client, m)
        try:
            print(f"\n  {m}{inspect.signature(fn)}")
        except (TypeError, ValueError):
            print(f"\n  {m} (сигнатура недоступна)")
        if fn.__doc__:
            print(f"    {fn.__doc__.strip()[:300]}")

    print("\n" + "=" * 60)
    print("Сигнатура get_activities (може містити офери в стрічці подій):")
    if hasattr(client, "get_activities"):
        print(inspect.signature(client.get_activities))
        if client.get_activities.__doc__:
            print(client.get_activities.__doc__.strip()[:500])


if __name__ == "__main__":
    main()
