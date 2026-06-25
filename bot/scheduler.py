import os
from aiogram import Bot
from dotenv import load_dotenv
from services import get_all_users, get_sales_today
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()  # Завантаження змінних середовища з файлу .env
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
    
async def send_report():
    users = await get_all_users()
    qty, total = await get_sales_today()

    qty = qty or 0
    total = total or 0

    text = f"""
📊 Звіт за день:

Продано: {qty}
Виручка: {total} грн
"""

    for chat_id in users:
        try:
            await bot.send_message(chat_id, text)
        except Exception as e:
            print(f"Не вдалося відправити {chat_id}: {e}")

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_report, "cron", hour=21)
    scheduler.start()