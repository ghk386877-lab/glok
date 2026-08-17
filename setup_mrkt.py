"""
ОДНОРАЗОВИЙ скрипт: створює файл сесії для MRKT (бібліотека amrkt).

Перед запуском:
1. Зайди на https://my.telegram.org/apps
2. Залогінься своїм номером телефону
3. Заповни коротку форму (App title / Short name - можна будь-що, наприклад
   "portals bot" / "portalsbot")
4. Отримаєш api_id (число) і api_hash (довгий рядок) - встав їх у .env:
   MRKT_API_ID=...
   MRKT_API_HASH=...

Запуск:
    python setup_mrkt.py

Скрипт попросить номер телефону (у форматі +380...) і код підтвердження,
який прийде в Telegram (не SMS!). Якщо в акаунті увімкнена двофакторна
автентифікація - попросить ще й пароль. Це все відбувається один раз:
після успішного логіну з'явиться файл сесії (за замовчуванням
"mrkt_session.session") поруч зі скриптом, і надалі бот
використовуватиме саме його, без повторного логіну.

УВАГА: файл сесії - це фактично ключ доступу до твого Telegram-акаунту.
Не публікуй його і не додавай у git (уже є в .gitignore: *.session).
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("MRKT_API_ID")
API_HASH = os.getenv("MRKT_API_HASH")
SESSION_NAME = os.getenv("MRKT_SESSION_NAME", "mrkt_session")


async def main() -> None:
    if not API_ID or not API_HASH:
        print(
            "Спочатку задай MRKT_API_ID і MRKT_API_HASH у .env "
            "(отримати на https://my.telegram.org/apps)"
        )
        return

    from amrkt import MarketClient

    print(f"Створюю/перевіряю сесію '{SESSION_NAME}'...")
    print("Зараз попросить номер телефону і код з Telegram - це нормально, один раз.\n")

    client = MarketClient(api_id=int(API_ID), api_hash=API_HASH, session_name=SESSION_NAME)
    async with client:
        user = await client.get_user_info()
        print(f"\nУспішно! Залогінено як: {user.full_name}")
        print(f"Файл сесії '{SESSION_NAME}.session' збережено поруч зі скриптом.")
        print("Тепер можна запускати inspect_mrkt.py і сам бот без повторного логіну.")


if __name__ == "__main__":
    asyncio.run(main())
