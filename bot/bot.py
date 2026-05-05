import os
import asyncio
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiosqlite
from config import BOT_TOKEN
from db import DB_NAME, init_db
from clasess import AddItem, RemoveItem
from services import get_sales_all_time, get_sales_last_days, get_sales_today
from scheduler import start_scheduler



bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def ensure_dirs():
    os.makedirs("images", exist_ok=True)

BTN_WAREHOUSE = "📦 Склад"
BTN_SALES = "💰 Продажі"
BTN_REPORT = "📊 Звіт"

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_WAREHOUSE)],
        [KeyboardButton(text=BTN_SALES)],
        [KeyboardButton(text=BTN_REPORT)]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот запущений 🚀")
    chat_id = message.chat.id
    username = message.from_user.username

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (chat_id, username)
            VALUES (?, ?)
        """, (chat_id, username))
        await db.commit()
        # await message.answer("Ти зареєстрований в системі ✅")

    
    await message.answer("Головне меню:", reply_markup=main_keyboard)
    await message.answer(
        "Команди:\n"
        "/warehouse — склад\n"
        "/sales — продажі сьогодні\n"
        "/report — звіт (сьогодні/7 днів/всього)"
    )


@dp.message(Command("warehouse"))
@dp.message(lambda message: message.text == BTN_WAREHOUSE)
@dp.message(lambda message: (message.text or "").strip().lower() == "склад")
async def warehouse(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT product_name, quantity, price FROM warehouse") as cur:
            rows = await cur.fetchall()

    if not rows:
        await message.answer("Склад пустий")
        return

    text = "📦 Склад:\n\n"
    for name, qty, price in rows:
        text += f"{name} — {qty} — {price} грн\n"

    await message.answer(text)

@dp.message(Command("add_item"))
async def start_add_item(message: types.Message, state: FSMContext):
    await state.set_state(AddItem.name)
    await message.answer("🧸 Введи назву товару:")


@dp.message(AddItem.name)
async def add_item_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip().lower())
    await state.set_state(AddItem.quantity)
    await message.answer("📦 Введи кількість:")


@dp.message(AddItem.quantity)
async def add_item_quantity(message: types.Message, state: FSMContext):
    try:
        qty = int(message.text)
    except Exception:
        return await message.answer("❌ Введи число")

    if qty <= 0:
        return await message.answer("❌ Кількість має бути > 0")

    await state.update_data(quantity=qty)
    await state.set_state(AddItem.price)
    await message.answer("💰 Введи ціну:")


@dp.message(AddItem.price)
async def add_item_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
    except Exception:
        return await message.answer("❌ Введи число")

    if price < 0:
        return await message.answer("❌ Ціна не може бути < 0")

    data = await state.get_data()
    name = data["name"]
    qty = data["quantity"]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO warehouse (product_name, quantity, price)
            VALUES (?, ?, ?)
            ON CONFLICT(product_name)
            DO UPDATE SET
                quantity = quantity + excluded.quantity,
                price = excluded.price
        """, (name, qty, price))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Додано:\n{name}\n{qty} шт\n{price} грн")

@dp.message(Command("remove_item"))
async def start_remove(message: types.Message, state: FSMContext):
    await state.set_state(RemoveItem.name)
    await message.answer("🗑 Введи назву товару для видалення:")


@dp.message(RemoveItem.name)
async def remove_item_name(message: types.Message, state: FSMContext):
    name = message.text.strip().lower()

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM warehouse WHERE product_name=?",
            (name,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        await state.clear()
        return await message.answer("❌ Товар не знайдено")

    await state.update_data(name=name, qty=row[0])
    await state.set_state(RemoveItem.confirm)
    await message.answer(f"⚠️ Видалити товар?\n\n{name} — {row[0]} шт\n\nНапиши: YES або NO")


@dp.message(RemoveItem.confirm)
async def remove_item_confirm(message: types.Message, state: FSMContext):
    answer = message.text.strip().lower()
    data = await state.get_data()
    name = data["name"]

    if answer == "no":
        await state.clear()
        return await message.answer("❎ Скасовано")

    if answer != "yes":
        return await message.answer("Напиши YES або NO")

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM warehouse WHERE product_name=?", (name,))
        await db.commit()

    await state.clear()
    await message.answer(f"🗑 Товар {name} видалено (обнулено)")


@dp.message(Command("sales"))
@dp.message(lambda message: message.text == BTN_SALES)
@dp.message(lambda message: (message.text or "").strip().lower() in {"продажі", "продажи"})
async def sales(message: types.Message):
    qty, total = await get_sales_today()

    qty = qty or 0
    total = total or 0

    note = ""
    if qty == 0 and total == 0:
        note = (
            "\n\nℹ️ Продажі зʼявляться після 2+ аналізів фото, "
            "коли кількість іграшок на полиці зменшиться.\n"
            "Також перевір, що на складі є товар `toy` з ціною (через /add_item)."
        )

    await message.answer(
        f"💰 Сьогодні:\nПродано: {qty}\nВиручка: {total} грн{note}"
    )

@dp.message(Command("report"))
@dp.message(lambda message: message.text == BTN_REPORT)
@dp.message(lambda message: (message.text or "").strip().lower() in {"звіт", "звітність", "отчет", "звiт"})
async def report(message: types.Message):
    qty_today, total_today = await get_sales_today()
    qty_7d, total_7d = await get_sales_last_days(7)
    qty_all, total_all = await get_sales_all_time()

    qty_today = qty_today or 0
    total_today = total_today or 0
    qty_7d = qty_7d or 0
    total_7d = total_7d or 0
    qty_all = qty_all or 0
    total_all = total_all or 0

    note = ""
    if qty_today == 0 and total_today == 0 and qty_7d == 0 and total_7d == 0 and qty_all == 0 and total_all == 0:
        note = (
            "\n\nℹ️ Зараз база продажів порожня. "
            "Продаж фіксується, коли нове фото показує менше іграшок, ніж на попередньому."
        )

    await message.answer(
        "📊 Звіт:\n\n"
        f"Сьогодні: {qty_today} шт / {total_today} грн\n"
        f"7 днів: {qty_7d} шт / {total_7d} грн\n"
        f"Всього: {qty_all} шт / {total_all} грн"
        f"{note}"
    )

async def send_to_api(file_path):
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=os.path.basename(file_path))
            
            async with session.post('http://127.0.0.1:8080/process-inventory/', data=data) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type.lower():
                    return await resp.json(), resp.status, None
                return None, resp.status, await resp.text()

@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    await message.answer("🔍 Обробляю зображення, зачекайте...")
    os.makedirs("images", exist_ok=True)
    
    photo = message.photo[-1]
    filename = f"images/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    
    # Завантажуємо фото локально
    await bot.download(photo, destination=filename)

    try:
        # Відправляємо на API
        result, status, raw_text = await send_to_api(filename)
        
        if status != 200:
            extra = f"\n\nВідповідь сервера:\n{raw_text}" if raw_text else ""
            return await message.answer(f"❌ API помилка: HTTP {status}{extra}")

        if result and result.get("status") == "ok":
            text = (
                f"✅ Аналіз завершено!\n\n"
                f"🧸 Виявлено іграшок: {result['detected_toys']}\n"
                f"💸 Продано з минулого разу: {result['sold_count']} шт\n"
                f"💰 Виручка: {result['total_earned']} грн"
            )
            await message.answer(text)
        else:
            extra = f"\n\nВідповідь сервера:\n{raw_text}" if raw_text else ""
            await message.answer(f"❌ Помилка при обробці API{extra}")
            
    except Exception as e:
        await message.answer(f"🚀 Помилка зв'язку з сервером: {e}")

async def main():
    ensure_dirs()
    await init_db()
    start_scheduler()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
