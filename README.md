# bot_toy_accounting

Проєкт для обліку іграшок:

- Telegram-бот приймає фото, показує склад, продажі та звіти.
- FastAPI-сервер обробляє фото і рахує іграшки через AI-модель.
- Дані зберігаються в SQLite-файлі `database.db`.

## Структура

- `bot/` - Telegram-бот.
- `backend/` - API для обробки фото.
- `backend/api/Ai/models/` - файли AI-моделей.
- `database.db` - база даних.
- `images/` і `bot/images/` - збережені фото.

## Перший запуск

1. Відкрий термінал у папці проєкту:

```bash
cd \bot_toy_accounting
```

2. Встанови Python-залежності:

```bash
pip install fastapi uvicorn python-multipart easyocr aiogram aiohttp aiosqlite apscheduler python-dotenv
pip install -r backend/api/Ai/requirements.txt
```

3. Створи або перевір файл `bot/.env`:

```env
BOT_TOKEN=твій_telegram_bot_token
```

## Як запускати

Потрібно відкрити два термінали.

### 1. Запустити API

```bash
python -m uvicorn backend.api.toy_inventory_api:app --host 0.0.0.0 --port 8080
```

API буде працювати на:

```text
http://127.0.0.1:8080
```

### 2. Запустити бота

В іншому терміналі:

```bash
python bot/bot.py
```

Після цього відкрий свого Telegram-бота і напиши:

```text
/start
```

## Команди бота

- `/start` - запустити бота.
- `/warehouse` - показати склад.
- `/add_item` - додати товар на склад.
- `/remove_item` - видалити товар зі складу.
- `/sales` - продажі за сьогодні.
- `/report` - звіт за сьогодні, 7 днів і весь час.

## Як користуватись

1. Запусти API.
2. Запусти Telegram-бота.
3. Додай товари через `/add_item`, якщо потрібно.
4. Надішли боту фото вітрини.
5. Бот відправить фото в API, API порахує іграшки, а бот покаже результат.

## База даних

Проєкт використовує файл:

```text
database.db
```

Якщо видалити цей файл, база створиться заново при запуску API або бота, але старі дані зникнуть.

## Якщо щось не працює

- Перевір, що API запущений на порту `8080`.
- Перевір, що в `bot/.env` є правильний `BOT_TOKEN`.
- Перевір, що встановлені всі залежності.
- Якщо бот не обробляє фото, спочатку запусти API, а потім бота.
