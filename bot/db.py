import aiosqlite
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent  # .../bot_toy_accounting
DB_NAME = str(PROJECT_ROOT / "database.db")

DEFAULT_TOYS = {
    "toy_1": 40,
    "toy_2": 70,
    "toy_3": 100,
    "toy_4": 250,
    "toy_5": 300,
    "toy_6": 350,
    "toy_7": 150,
}

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
        
        await db.executemany("""
        INSERT OR IGNORE INTO warehouse (product_name, quantity, price)
        VALUES (?, ?, ?)
        """, [(name, 0, float(price)) for name, price in DEFAULT_TOYS.items()])

        await db.executemany("""
        INSERT OR IGNORE INTO shelf (product_name, quantity)
        VALUES (?, ?)
        """, [(name, 0) for name in DEFAULT_TOYS.keys()])

        await db.commit()
