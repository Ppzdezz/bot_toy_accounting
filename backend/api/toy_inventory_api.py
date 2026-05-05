import os
import sys
import pathlib # Додаємо це
from fastapi import FastAPI, File, Path, UploadFile # Path тут залишається для FastAPI
import sqlite3
import cv2
import easyocr
import json
from datetime import datetime
from fastapi.responses import JSONResponse

from backend.api.Ai.detect_toys import ToyEnsembleDetector

# Paths / storage (module-level so they are ready during startup)
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = next(
    (p for p in [CURRENT_DIR, *CURRENT_DIR.parents] if (p / "backend").is_dir() and (p / "bot").is_dir()),
    CURRENT_DIR.parents[2],
)
UPLOAD_DIR = str(CURRENT_DIR / "uploads")
DB_NAME = str(PROJECT_ROOT / "database.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": str(exc)},
    )


def init_db():
    conn = sqlite3.connect(DB_NAME)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS warehouse (
                product_name TEXT PRIMARY KEY,
                quantity INTEGER,
                price REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shelf (
                product_name TEXT PRIMARY KEY,
                quantity INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                quantity INTEGER,
                total_price REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT
            )
        """)
        conn.commit()
        print("[init_db] ensured tables exist")

        # Ensure default product used by AI flow exists.
        cur.execute("""
            INSERT OR IGNORE INTO warehouse (product_name, quantity, price)
            VALUES (?, ?, ?)
        """, ("toy", 0, 0.0))
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
async def on_startup():
    init_db()
    print(f"[startup] DB_NAME={DB_NAME}")
    print(f"[startup] cwd={os.getcwd()}")
    print(f"[startup] __file__={__file__}")
    print(f"[startup] CURRENT_DIR={CURRENT_DIR}")
    print(f"[startup] PROJECT_ROOT={PROJECT_ROOT}")

# Будуємо шлях до моделей
MODEL10_PATH = CURRENT_DIR / "Ai" / "models" / "best_v10.pt"
MODEL11_PATH = CURRENT_DIR / "Ai" / "models" / "best_v11.pt"

# Ініціалізація детектора
detector = ToyEnsembleDetector(
    model10_path=str(MODEL10_PATH),
    model11_path=str(MODEL11_PATH)
)

reader = easyocr.Reader(['en'])

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.post("/process-inventory/")
async def process_inventory(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())


    detection_result = detector.detect(file_path)
    
    new_qty = len(detection_result["toys"])
    product_label = "toy" 

   
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sold_count = 0
    total_earned = 0

    cursor.execute("SELECT quantity FROM shelf WHERE product_name=?", (product_label,))
    row = cursor.fetchone()
    old_qty = row['quantity'] if row else 0

    if old_qty > new_qty:
        sold_count = old_qty - new_qty
        
        cursor.execute("SELECT price FROM warehouse WHERE product_name=?", (product_label,))
        p_row = cursor.fetchone()
        price = p_row['price'] if p_row else 0
        
        cursor.execute(
            "INSERT INTO sales (product_name, quantity, total_price) VALUES (?, ?, ?)",
            (product_label, sold_count, sold_count * price)
        )
        total_earned = sold_count * price

    
    img = cv2.imread(file_path)
    for tag in detection_result["price_tags"]:
        x1, y1, x2, y2 = tag["bbox"]
        roi = img[y1:y2, x1:x2]
        ocr_res = reader.readtext(roi)
        if ocr_res:
            print(f"Знайдена ціна на фото: {ocr_res[0][1]}")

    cursor.execute(
        "INSERT OR REPLACE INTO shelf (product_name, quantity) VALUES (?, ?)",
        (product_label, new_qty)
    )

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "detected_toys": new_qty,
        "sold_count": sold_count,
        "total_earned": total_earned,
        "details": detection_result
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 
