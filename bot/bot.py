import os
import asyncio
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
from services import *
from scheduler import start_scheduler



bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def ensure_dirs():
    os.makedirs("images", exist_ok=True)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Склад")],
        [KeyboardButton(text="💰 Продажі")],
        [KeyboardButton(text="📊 Звіт")]
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

    
    await message.answer("Головне меню:", reply_markup = main_keyboard)


@dp.message(lambda message: message.text == "📦 Склад")
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
    async def process_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)

        await state.set_state(AddItem.quantity)
        await message.answer("📦 Введи кількість:")

    @dp.message(AddItem.quantity)
    async def process_quantity(message: types.Message, state: FSMContext):
        try:
            qty = int(message.text)
        except:
            return await message.answer("❌ Введи число")

        await state.update_data(quantity=qty)

        await state.set_state(AddItem.price)
        await message.answer("💰 Введи ціну:")

    @dp.message(AddItem.price)
    async def process_price(message: types.Message, state: FSMContext):
        try:
            price = float(message.text)
        except:
            return await message.answer("❌ Введи число")

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

        await message.answer(
            f"✅ Додано:\n{name}\n{qty} шт\n{price} грн"
        )

@dp.message(Command("remove_item"))
async def start_remove(message: types.Message, state: FSMContext):
    await state.set_state(RemoveItem.name)
    await message.answer("🗑 Введи назву товару для видалення:")

    @dp.message(RemoveItem.name)
    async def get_item(message: types.Message, state: FSMContext):
        name = message.text.lower()

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

        await message.answer(
            f"⚠️ Видалити товар?\n\n{name} — {row[0]} шт\n\nНапиши: YES або NO"
        )

    @dp.message(RemoveItem.confirm)
    async def confirm_delete(message: types.Message, state: FSMContext):
        answer = message.text.lower()
        data = await state.get_data()
        name = data["name"]

        if answer == "no":
            await state.clear()
            return await message.answer("❎ Скасовано")

        if answer != "yes":
            return await message.answer("Напиши YES або NO")

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                DELETE FROM warehouse WHERE product_name=?
            """, (name,))
            await db.commit()

        await state.clear()

        await message.answer(f"🗑 Товар {name} видалено (обнулено)")


@dp.message(lambda message: message.text == "💰 Продажі")
async def sales(message: types.Message):
    qty, total = await get_sales_today()

    qty = qty or 0
    total = total or 0

    await message.answer(
        f"💰 Сьогодні:\nПродано: {qty}\nВиручка: {total} грн"
    )

@dp.message(lambda message: message.text == "📊 Звіт")
async def report(message: types.Message):
    qty, total = await get_sales_today()

    qty = qty or 0
    total = total or 0

    await message.answer(
        f"📊 Звіт:\nПродано: {qty}\nВиручка: {total} грн"
    )

@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    os.makedirs("images", exist_ok=True)  # ✅ створює папку якщо нема

    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    file_path = file.file_path

    filename = f"images/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

    await bot.download_file(file_path, filename)

    await message.answer_photo(photo.file_id, caption="Отримано")

async def main():
    ensure_dirs()
    await init_db()
    start_scheduler()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())