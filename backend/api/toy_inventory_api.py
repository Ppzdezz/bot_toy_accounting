import os
import sys
import pathlib
from fastapi import FastAPI, File, Path, UploadFile
import sqlite3
import cv2
import easyocr
import json
import re
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

DEFAULT_TOYS = {
    "toy_1": 40,
    "toy_2": 70,
    "toy_3": 100,
    "toy_4": 250,
    "toy_5": 300,
    "toy_6": 350,
    "toy_7": 150,
}
LEGACY_TOY_NAME = "toy"
DEFAULT_TOY_FALLBACK = "toy_1"


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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_sales (
                product_name TEXT PRIMARY KEY,
                old_qty INTEGER NOT NULL,
                new_qty INTEGER NOT NULL,
                confirm_count INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[init_db] ensured tables exist")

        # Seed default toy types with price and empty quantities.
        cur.executemany("""
            INSERT OR IGNORE INTO warehouse (product_name, quantity, price)
            VALUES (?, ?, ?)
        """, [(name, 0, float(price)) for name, price in DEFAULT_TOYS.items()])
        cur.executemany("""
            INSERT OR IGNORE INTO shelf (product_name, quantity)
            VALUES (?, ?)
        """, [(name, 0) for name in DEFAULT_TOYS.keys()])
        # Backward compatibility for existing logic that uses "toy".
        cur.execute("""
            INSERT OR IGNORE INTO warehouse (product_name, quantity, price)
            VALUES (?, ?, ?)
        """, (LEGACY_TOY_NAME, 0, float(DEFAULT_TOYS[DEFAULT_TOY_FALLBACK])))
        cur.execute("""
            UPDATE warehouse
            SET price = ?
            WHERE product_name = ? AND (price IS NULL OR price = 0)
        """, (float(DEFAULT_TOYS[DEFAULT_TOY_FALLBACK]), LEGACY_TOY_NAME))
        cur.execute("""
            INSERT OR IGNORE INTO shelf (product_name, quantity)
            VALUES (?, ?)
        """, (LEGACY_TOY_NAME, 0))
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


MODEL10_PATH = CURRENT_DIR / "Ai" / "models" / "best_v10.pt"
MODEL11_PATH = CURRENT_DIR / "Ai" / "models" / "best_v11.pt"


detector = ToyEnsembleDetector(
    model10_path=str(MODEL10_PATH),
    model11_path=str(MODEL11_PATH)
)

reader = easyocr.Reader(['en'])


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def extract_price_value(text: str):
    if not text:
        return None
    match = re.search(r"(\d{2,4})", text.replace(" ", ""))
    return int(match.group(1)) if match else None


def nearest_price_tag(toy_bbox, price_tags):
    t_x1, t_y1, t_x2, t_y2 = toy_bbox
    toy_center_x = (t_x1 + t_x2) / 2
    toy_center_y = (t_y1 + t_y2) / 2

    nearest_tag = None
    nearest_distance = None
    for tag in price_tags:
        p_x1, p_y1, p_x2, p_y2 = tag["bbox"]
        tag_center_x = (p_x1 + p_x2) / 2
        tag_center_y = (p_y1 + p_y2) / 2
        distance = ((toy_center_x - tag_center_x) ** 2 + (toy_center_y - tag_center_y) ** 2) ** 0.5
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_tag = tag
    return nearest_tag, nearest_distance


@app.post("/process-inventory/")
async def process_inventory(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    detection_result = detector.detect(file_path)

    conn = get_db_connection()
    cursor = conn.cursor()

    img = cv2.imread(file_path)
    if img is None:
        conn.close()
        return {"status": "error", "error": f"Cannot read image: {file_path}"}

    # OCR for every visible price tag.
    for tag in detection_result["price_tags"]:
        x1, y1, x2, y2 = tag["bbox"]
        roi = img[y1:y2, x1:x2]
        ocr_res = reader.readtext(roi)
        text = " ".join([res[1] for res in ocr_res]) if ocr_res else ""
        tag["ocr_text"] = text
        tag["price_value"] = extract_price_value(text)
        if text:
            print(f"Знайдена ціна на фото: {text}")

    cursor.execute("SELECT product_name, price FROM warehouse")
    warehouse_rows = cursor.fetchall()
    product_by_price = {
        int(row["price"]): row["product_name"]
        for row in warehouse_rows
        if row["price"] is not None and row["product_name"] != LEGACY_TOY_NAME
    }

    visible_products = set()
    for tag in detection_result["price_tags"]:
        price_value = tag.get("price_value")
        if price_value is None:
            continue
        product_label = product_by_price.get(int(price_value))
        if product_label:
            visible_products.add(product_label)

    verified_toys = []
    new_qty_by_product = {product_label: 0 for product_label in visible_products}

    # Assign each toy to nearest price tag and map by OCR'ed price to product_name.
    for toy in detection_result["toys"]:
        nearest_tag, nearest_distance = nearest_price_tag(toy["bbox"], detection_result["price_tags"])
        if not nearest_tag or nearest_distance is None or nearest_distance > 170:
            continue

        price_value = nearest_tag.get("price_value")
        if price_value is None:
            continue

        product_label = product_by_price.get(int(price_value))
        if not product_label:
            continue

        toy["matched_price"] = price_value
        toy["product_name"] = product_label
        verified_toys.append(toy)
        new_qty_by_product[product_label] = new_qty_by_product.get(product_label, 0) + 1

    sold_count = 0
    total_earned = 0
    sold_toy_price = 0
    sales_breakdown = []
    pending_verification = 0

    for product_label, new_qty in new_qty_by_product.items():
        cursor.execute("SELECT quantity FROM shelf WHERE product_name=?", (product_label,))
        row = cursor.fetchone()
        old_qty = row["quantity"] if row else 0

        cursor.execute("SELECT price FROM warehouse WHERE product_name=?", (product_label,))
        p_row = cursor.fetchone()
        unit_price = float(p_row["price"]) if p_row and p_row["price"] is not None else 0

        if old_qty > new_qty:
            # 2-step confirm logic is intentionally disabled.
            # cursor.execute(
            #     "SELECT old_qty, new_qty, confirm_count FROM pending_sales WHERE product_name=?",
            #     (product_label,)
            # )
            # pending = cursor.fetchone()
            # if pending and pending["old_qty"] == old_qty and pending["new_qty"] == new_qty:
            #     confirm_count = pending["confirm_count"] + 1
            #     cursor.execute(
            #         "UPDATE pending_sales SET confirm_count=?, updated_at=CURRENT_TIMESTAMP WHERE product_name=?",
            #         (confirm_count, product_label)
            #     )
            # else:
            #     confirm_count = 1
            #     cursor.execute(
            #         '''
            #         INSERT INTO pending_sales (product_name, old_qty, new_qty, confirm_count)
            #         VALUES (?, ?, ?, 1)
            #         ON CONFLICT(product_name) DO UPDATE SET
            #             old_qty=excluded.old_qty,
            #             new_qty=excluded.new_qty,
            #             confirm_count=1,
            #             updated_at=CURRENT_TIMESTAMP
            #         ''',
            #         (product_label, old_qty, new_qty)
            #     )
            # pending_verification += 1
            # if confirm_count >= 2:
            sold_delta = old_qty - new_qty
            earned_delta = sold_delta * unit_price
            cursor.execute(
                "INSERT INTO sales (product_name, quantity, total_price) VALUES (?, ?, ?)",
                (product_label, sold_delta, earned_delta)
            )
            sold_count += sold_delta
            total_earned += earned_delta
            sold_toy_price = unit_price
            sales_breakdown.append({
                "product_name": product_label,
                "sold_count": sold_delta,
                "price": unit_price,
                "earned": earned_delta,
            })
            cursor.execute("DELETE FROM pending_sales WHERE product_name=?", (product_label,))
            cursor.execute(
                "INSERT OR REPLACE INTO shelf (product_name, quantity) VALUES (?, ?)",
                (product_label, new_qty)
            )
        else:
            cursor.execute("DELETE FROM pending_sales WHERE product_name=?", (product_label,))
            cursor.execute(
                "INSERT OR REPLACE INTO shelf (product_name, quantity) VALUES (?, ?)",
                (product_label, new_qty)
            )

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "detected_toys": len(verified_toys),
        "sold_count": sold_count,
        "sold_toy_price": sold_toy_price,
        "total_earned": total_earned,
        "pending_verification": pending_verification,
        "sales_breakdown": sales_breakdown,
        "details": {
            "toys": verified_toys,
            "price_tags": detection_result["price_tags"]
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
