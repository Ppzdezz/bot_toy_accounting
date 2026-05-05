import aiosqlite
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent  # .../bot_toy_accounting
DB_NAME = str(PROJECT_ROOT / "database.db")

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS warehouse (
            product_name TEXT PRIMARY KEY,
            quantity INTEGER,
            price REAL NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS shelf (
            product_name TEXT PRIMARY KEY,
            quantity INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            quantity INTEGER,
            total_price REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            image_path TEXT
        )
        """)
        
        await db.commit()
