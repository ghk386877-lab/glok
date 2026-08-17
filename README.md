# Portals Gift Monitor Bot

Telegram-бот, який моніторить подарунки на маркетплейсі **Portals**:
floor-ціни та їх зміну, топ за об'ємом торгів за 24 год, фільтр по цінових
діапазонах у TON (0-3 / 3-10 / 10-20).

Бот використовує бібліотеку [`aportalsmp`](https://pypi.org/project/aportalsmp/) —
неофіційну, реверс-інжинірингову обгортку над внутрішнім API Portals
(офіційного публічного API немає, бо Portals - це Telegram Mini App).

## 1. Встановлення

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Заповни у `.env`:
- `BOT_TOKEN` — токен від @BotFather
- `ADMIN_IDS` — твій Telegram user id (дізнатись можна у @userinfobot)

## 2. Як отримати authData Portals

Portals вимагає авторизований запит для кожного виклику API. Найпростіший спосіб:

1. Відкрий https://web.telegram.org у браузері (Chrome/Firefox).
2. Зайди у чат/mini app Portals так, щоб міні-застосунок відкрився всередині Telegram Web.
3. Відкрий DevTools (F12) → вкладка **Network**.
4. Знайди запит до `portal-market.com`, наприклад `portal-market.com/api/nfts/search`
   (це основний ендпоінт пошуку лотів, саме на нього варто дивитись).
5. У заголовках запиту (**Request Headers**) знайди `Authorization`.
   Значення виглядає як `tma query_id=...&user=...&auth_date=...&hash=...`.
6. Скопіюй **все значення повністю, разом зі словом `tma` на початку**.

Це значення живе обмежений час (за спостереженнями спільноти — від 1 до 7 днів),
після чого потрібно повторити кроки і оновити його.

## 3. Структура даних підтверджена

Реальні поля Portals API (перевірено `debug_inspect.py` 09.07.2026):

- `name` — назва подарунка
- `floor_price` — поточна floor-ціна, TON (рядок, конвертується в float)
- `day_volume` — обсяг торгів за 24 год, TON
- `sales_24h_count` — кількість угод за 24 год
- `supply`, `market_cap`, `listed_count` — додаткова інформація

Якщо Portals колись змінить ці назви - онови `_NAME_KEYS/_FLOOR_KEYS/_VOLUME_KEYS/_SALES_COUNT_KEYS`
у `monitor.py`. Можна знову звірити командою:

```bash
python debug_inspect.py "tma твій_токен"
```

## 4. Запуск бота

```bash
python main.py
```

Після старту напиши боту в Telegram:

```
/setauth tma твій_скопійований_токен
```

(тільки з акаунту, id якого вказано в `ADMIN_IDS`).

Далі бот сам періодично (кожні `POLL_INTERVAL_SECONDS`) опитуватиме Portals
і накопичуватиме історію цін у SQLite (`portals.db`), потрібну для розрахунку
"% зміни за 24 год".

## 5. Команди бота

| Команда | Що робить |
|---|---|
| `/floors` | Усі подарунки: floor-ціна (TON) + зміна за 24 год |
| `/volume` | Топ подарунків за об'ємом торгів за 24 год |
| `/range 0-3` | Подарунки з floor-ціною від 0 до 3 TON |
| `/range 3-10` | Подарунки з floor-ціною від 3 до 10 TON |
| `/range 10-20` | Подарунки з floor-ціною від 10 до 20 TON |
| `/subscribe` | Отримувати сповіщення про різку зміну floor-ціни (поріг - `ALERT_THRESHOLD_PERCENT`) |
| `/unsubscribe` | Вимкнути ці сповіщення |
| `/setauth <tma ...>` | Оновити authData (тільки адмін) |
| `/poll` | Примусово оновити дані просто зараз (тільки адмін) |
| `/status` | Перевірити стан бота |

## 6. Деплой на Railway (щоб бот працював 24/7 без комп'ютера)

Бот повністю керується командами в Telegram (включно з оновленням `authData`
через `/setauth`), тож для нього не потрібен доступ до консолі сервера
день у день - тільки один раз для початкового налаштування.

### Крок 1 - Заливаєш код у GitHub

```bash
cd portals_bot
git init
git add .
git commit -m "Portals gift monitor bot"
```

Створи новий репозиторій на GitHub і запуш туди (`git remote add origin ...`,
`git push -u origin main`). Файл `.gitignore` вже подбає, щоб `.env` і
`portals.db` туди не потрапили.

### Крок 2 - Створюєш проєкт на Railway

1. На https://railway.com → **New Project** → **Deploy from GitHub repo** →
   обираєш свій репозиторій.
2. Railway сам розпізнає Python-проєкт (Nixpacks) і підхопить `Procfile`/`railway.json`,
   які вже лежать у репозиторії - запустить `python main.py` як фоновий worker
   (без HTTP-порту, він тут і не потрібен, бот сам ходить у Telegram по polling).

### Крок 3 - Змінні середовища

У Railway: вкладка **Variables** проєкту → додай ті самі значення, що і в `.env`:

```
BOT_TOKEN=...
ADMIN_IDS=...
POLL_INTERVAL_SECONDS=300
ALERT_THRESHOLD_PERCENT=7
DB_PATH=/data/portals.db
MRKT_API_ID=...
MRKT_API_HASH=...
MRKT_SESSION_NAME=mrkt_session
PORTALS_AUTH_SESSION_NAME=portals_auth_session
PORTALS_AUTH_REFRESH_INTERVAL_SECONDS=86400
PORTALS_FEE_PERCENT=2
MRKT_FEE_PERCENT=2
PORTALS_WITHDRAW_FEE_TON=0.3
MRKT_WITHDRAW_FEE_TON=0.25
MIN_SALES_24H_FOR_VALID=10
```

`PORTALS_AUTH_DATA` можна не задавати - authData тепер оновлюється повністю
автоматично через Pyrogram-сесію (розділ нижче).

### Крок 3.5 - Перенесення файлів сесій (MRKT + автооновлення Portals)

Локально в тебе вже є два файли: `mrkt_session.session` і
`portals_auth_session.session`. Railway їх не бачить (це файли на твоєму
диску, не в git), тому переносимо через Base64 у змінні середовища - бот
сам розпакує їх при кожному старті контейнера (`session_bootstrap.py`).

1. У PowerShell, у папці проєкту, виконай (кодує файл і одразу копіює в буфер обміну):
   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("mrkt_session.session")) | Set-Clipboard
   ```
2. У Railway Variables додай `MRKT_SESSION_B64` → встав те, що скопіювалось (Ctrl+V).
3. Повтори те саме для другого файлу:
   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("portals_auth_session.session")) | Set-Clipboard
   ```
   → додай як `PORTALS_AUTH_SESSION_B64` у Railway Variables.

Ці файли сесій НЕ потребують persistent Volume (на відміну від `portals.db`) -
вони детерміновано відновлюються з Base64-змінної при кожному старті
контейнера, навіть після редеплою.

### Крок 4 - Volume для бази даних (ОБОВ'ЯЗКОВО)

Без цього кроку `portals.db` (історія цін для розрахунку "% за 24 год" і
для сповіщень про різку зміну ціни) буде зникати при кожному редеплої, бо
файлова система Railway ефемерна.

1. У проєкті на Railway: **Settings** → **Volumes** → **New Volume**.
2. Mount path: `/data`
3. Переконайся, що `DB_PATH=/data/portals.db` заданий у Variables (крок 3) -
   тоді SQLite писатиме саме у volume, а не у тимчасову файлову систему.

### Крок 5 - Перевірка

Після деплою подивись логи (вкладка **Deployments** → **View Logs**) -
має бути "Оновлюю authData Portals автоматично перед стартом..." і потім
"Бот запущений. Очікую команди...". Потім у Telegram: `/status`, `/poll`,
`/floors` - усе має запрацювати одразу, без ручного `/setauth`.

### Про authData надалі

Тепер усе оновлюється автоматично (розділ вище, кроки з setup_mrkt.py і
setup_portals_auth.py), включно з роботою на Railway. `/setauth` лишається
як запасний варіант на випадок, якщо автооновлення раптом відмовить.

### Важливо: тільки один запущений інстанс

Якщо після деплою на Railway ти ще й лишиш локальний `python main.py`
запущеним на своєму комп'ютері - отримаєш ту саму помилку `Conflict:
terminated by other getUpdates request`, що бачив раніше, бо два процеси з
одним токеном одночасно не можуть опитувати Telegram. Обери щось одне.

## 7. Mini App (Огляд / Арбітраж / Ордери)

Бот тепер має вбудований веб-сервер, який видає Mini App - працює в тому
самому процесі, окремий Railway-сервіс не потрібен.

### Локально

Просто запусти `python main.py` як завжди - веб-сервер підніметься сам на
порту 8080. Але Telegram Mini App **вимагає публічний HTTPS-домен**, тому
локально кнопку `/app` через Telegram не відкрити (можеш тільки перевірити,
що сторінка взагалі рендериться, відкривши `http://localhost:8080` у
звичайному браузері - дані підтягнуться, просто без теми Telegram).

### На Railway

1. Після деплою (розділ 6): **Settings → Networking → Generate Domain**.
   Railway видасть щось на кшталт `https://your-app.up.railway.app`.
2. Постав цей домен у Variables як `WEBAPP_URL=https://your-app.up.railway.app`.
3. Railway сам підхопить `$PORT` (env-змінну, яку сам і задає) - додаткових
   налаштувань порту не треба, `config.py` вже читає `$PORT` автоматично.
4. Перезапусти деплой (Redeploy), щоб змінна підхопилась.
5. У Telegram напиши боту `/app` - має прийти кнопка "Відкрити Mini App".

### Вкладки

- **Огляд** - floor-ціни, зміна за 24 год, фільтр по діапазонах TON, сортування за обсягом
- **Арбітраж** - Portals vs MRKT, найвигідніший напрямок купівлі (потребує підключеного MRKT)
- **Ордери** - офер → floor на Portals, з розрахунком прибутку після комісії

Арбітраж і Ордери можуть вантажитись 10-60 секунд (кожен подарунок - окремий
API-запит з паузою проти rate limit) - це нормально, не баг.

## 8. Обмеження і чесне попередження

- Це неофіційне API. Portals може змінити формат відповіді або заблокувати
  забагато запитів на хвилину — не став `POLL_INTERVAL_SECONDS` надто малим
  (300-600 секунд — розумний старт).
- `authData` — це, по суті, твоя сесія в Portals. Не публікуй її і не давай
  іншим людям, не додавай `.env` у git.
- "24 год" рахується як "найближчий знімок, зроблений ≥24 год тому", тобто
  точність залежить від того, як довго вже працює бот і як часто опитує дані.
  В перші 24 год після запуску зміна може показувати "н/д".

## Структура проєкту

```
config.py          - конфігурація з .env
auth_store.py       - authData, що можна оновлювати без перезапуску
portals_client.py    - обгортка над aportalsmp
monitor.py           - періодичне опитування Portals -> SQLite
storage.py           - SQLite: знімки floor-ціни/об'єму
reports.py           - побудова текстових звітів
bot.py               - обробники команд Telegram
main.py              - точка входу (планувальник + бот)
debug_inspect.py     - перевірка сирої структури відповіді API
```
