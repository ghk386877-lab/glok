"""
ОДНОРАЗОВИЙ скрипт: створює ОКРЕМИЙ файл сесії для автооновлення authData
Portals через update_auth() з aportalsmp.

Навіщо окрема сесія, а не та сама, що для MRKT? Pyrogram-сесії (SQLite-файли)
не розраховані на одночасне використання одразу двома Client-інстансами.
MRKT-клієнт весь час тримає з'єднання відкритим, поки бот працює - якщо
автооновлення Portals використовувало б той самий файл, це могло б викликати
конфлікти/помилки блокування бази. Окремий файл повністю усуває цю проблему.

Можеш увійти тим самим номером телефону, яким логінився для MRKT - Telegram
дозволяє кілька одночасних сесій одного акаунту (як зайти ще з одного
пристрою), це нормально і безпечно.

Використовує ті самі MRKT_API_ID/MRKT_API_HASH з .env.

Запуск:
    python setup_portals_auth.py
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("MRKT_API_ID")
API_HASH = os.getenv("MRKT_API_HASH")
SESSION_NAME = os.getenv("PORTALS_AUTH_SESSION_NAME", "portals_auth_session")


async def main() -> None:
    if not API_ID or not API_HASH:
        print(
            "Спочатку задай MRKT_API_ID і MRKT_API_HASH у .env "
            "(ті самі, що вже використав для setup_mrkt.py)"
        )
        return

    import aportalsmp

    print(f"Створюю сесію '{SESSION_NAME}' для автооновлення Portals authData...")
    print("Знову попросить номер телефону і код з Telegram - це останній раз.\n")

    new_auth = await aportalsmp.update_auth(
        api_id=int(API_ID),
        api_hash=API_HASH,
        session_name=SESSION_NAME,
    )

    print(f"\nУспішно! Отримано authData (перші 50 символів): {new_auth[:50]}...")
    print(f"Файл сесії '{SESSION_NAME}.session' збережено поруч зі скриптом.")
    print("Тепер бот буде оновлювати authData Portals повністю автоматично.")


if __name__ == "__main__":
    asyncio.run(main())
