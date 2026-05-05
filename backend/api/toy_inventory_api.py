import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
from fastapi import FastAPI, File, UploadFile
import sqlite3
import cv2
import easyocr
import json
from datetime import datetime
from backend.api.Ai.detect_toys import ToyEnsembleDetector

app = FastAPI()

UPLOAD_DIR = "uploads"
DB_NAME = "../../database.db" 
os.makedirs(UPLOAD_DIR, exist_ok=True)


detector = ToyEnsembleDetector(
    model10_path="Ai/models/best_v10.pt", 
    model11_path="Ai/models/best_v11.pt"
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
