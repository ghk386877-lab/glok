"""
Завантаження конфігурації з .env / змінних середовища.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
}
# authData можна задати одразу через .env, або пізніше командою /setauth
PORTALS_AUTH_DATA = os.getenv("PORTALS_AUTH_DATA", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
DB_PATH = os.getenv("DB_PATH", "portals.db")

# Якщо floor-ціна подарунка зміниться за один цикл опитування більше ніж на
# цей відсоток - бот надішле сповіщення всім, хто підписався через /subscribe
ALERT_THRESHOLD_PERCENT = float(os.getenv("ALERT_THRESHOLD_PERCENT", "7"))

# Цінові діапазони в TON (раніше - "GRAM"), як просив користувач
PRICE_RANGES = {
    "0-3": (0, 3),
    "3-10": (3, 10),
    "10-20": (10, 20),
}

# MRKT (amrkt) - потрібен api_id/api_hash з my.telegram.org + одноразовий
# логін через setup_mrkt.py, який створює файл сесії MRKT_SESSION_NAME.session
MRKT_API_ID = os.getenv("MRKT_API_ID", "")
MRKT_API_HASH = os.getenv("MRKT_API_HASH", "")
MRKT_SESSION_NAME = os.getenv("MRKT_SESSION_NAME", "mrkt_session")

# Окрема Pyrogram-сесія (той самий акаунт, інший файл!) для автооновлення
# authData Portals через aportalsmp.update_auth(). Окрема - щоб не було
# конфлікту з постійним з'єднанням MRKT-клієнта на тому самому файлі сесії.
PORTALS_AUTH_SESSION_NAME = os.getenv("PORTALS_AUTH_SESSION_NAME", "portals_auth_session")
# Як часто (в секундах) автоматично оновлювати authData Portals.
# Ендпоінти оферів (topOffer/allCollectionOffers) виявились суворішими до
# свіжості підпису, ніж /floors - тому оновлюємо частіше, ніж формальний
# термін життя токена (1-7 днів) міг би підказати.
PORTALS_AUTH_REFRESH_INTERVAL_SECONDS = int(
    os.getenv("PORTALS_AUTH_REFRESH_INTERVAL_SECONDS", str(60 * 60))
)

# Скільки рядків показувати в топах (/orders_top, /arbitrage_top, Mini App)
TOP_N_DISPLAY = int(os.getenv("TOP_N_DISPLAY", "20"))
# /orders_top окремо - користувач хотів більше саме тут
ORDERS_TOP_N = int(os.getenv("ORDERS_TOP_N", "30"))
# Скільки ліквідних кандидатів перевіряти перед відбором топу (більше -
# точніший топ, але довше виконання)
ORDERS_CANDIDATE_POOL = int(os.getenv("ORDERS_CANDIDATE_POOL", "90"))
ARBITRAGE_CANDIDATE_POOL = int(os.getenv("ARBITRAGE_CANDIDATE_POOL", "30"))
# /snipe_top - окремий, більший пул (сканування легше за арбітраж/ордери,
# один запит на колекцію, тож можна перевірити значно більше)
SNIPE_CANDIDATE_POOL = int(os.getenv("SNIPE_CANDIDATE_POOL", "80"))
# Скільки запитів до Portals/MRKT робити одночасно (паралельно), замість
# одного за раз з паузою - пришвидшує топи в кілька разів
API_CONCURRENCY_LIMIT = int(os.getenv("API_CONCURRENCY_LIMIT", "5"))

# Комісії маркетплейсів (%) і комісії за виведення подарунка (TON) - для
# розрахунку реального прибутку в арбітражі.
#
# Portals: покупець платить РІВНО вказану ціну; продавець отримує
#   floor_price * (1 - PORTALS_FEE_PERCENT/100).
# MRKT: продавець отримує РІВНО заявлену суму; покупець платить
#   amount * (1 + MRKT_FEE_PERCENT/100) - це і є різниця між
#   sale_price (з комісією, платить покупець) і sale_price_without_fee
#   (без комісії, отримує продавець), яку ми вже бачимо в даних MRKT.
PORTALS_FEE_PERCENT = float(os.getenv("PORTALS_FEE_PERCENT", "2"))
MRKT_FEE_PERCENT = float(os.getenv("MRKT_FEE_PERCENT", "2"))
PORTALS_WITHDRAW_FEE_TON = float(os.getenv("PORTALS_WITHDRAW_FEE_TON", "0.3"))
MRKT_WITHDRAW_FEE_TON = float(os.getenv("MRKT_WITHDRAW_FEE_TON", "0.25"))

# Мінімальна кількість продажів за 24 год, щоб подарунок вважався "валідним"
# (ліквідним) для показу в /orders_top і /arbitrage_top - відсікає рідкісні
# колекції, де флор/офер ненадійні через малий об'єм торгів.
MIN_SALES_24H_FOR_VALID = int(os.getenv("MIN_SALES_24H_FOR_VALID", "10"))

# Mini App: порт для веб-сервера (Railway сам задає $PORT для сервісів з
# відкритим портом) і публічний URL (для кнопки /app - береш з Railway
# після першого деплою, вкладка Settings -> Networking -> Generate Domain)
WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080")))
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не заданий. Скопіюй .env.example у .env і заповни значення."
    )
