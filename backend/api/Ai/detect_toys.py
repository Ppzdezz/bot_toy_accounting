from ultralytics import YOLO
import torch
import cv2
import json
from typing import Dict, List, Any
from pathlib import Path

class ToyEnsembleDetector:
    def __init__(self, model10_path: str, model11_path: str):
        print("🔄 Завантаження моделей...")
        self.model10 = YOLO(model10_path)
        self.model11 = YOLO(model11_path)
        self.names = self.model11.names
        print("✅ Моделі завантажено успішно!")

    def detect(self, image_path: str, conf: float = 0.35, iou: float = 0.42) -> Dict[str, List[Dict]]:
        res10 = self.model10.predict(image_path, conf=conf, imgsz=1024, augment=True, verbose=False)[0]
        res11 = self.model11.predict(image_path, conf=conf, imgsz=1024, augment=True, verbose=False)[0]
        
        all_boxes, all_scores, all_cls = [], [], []
        for res in [res10, res11]:
            if len(res.boxes) > 0:
                all_boxes.append(res.boxes.xyxy)
                all_scores.append(res.boxes.conf)
                all_cls.append(res.boxes.cls)

        if not all_boxes:
            return {"toys": [], "price_tags": []}

        boxes = torch.cat(all_boxes, 0)
        scores = torch.cat(all_scores, 0)
        cls_ids = torch.cat(all_cls, 0)

        try:
            from torchvision.ops import nms
            keep = nms(boxes, scores, iou)
        except:
            keep = torch.arange(len(boxes))

        h = res11.orig_shape[0]
        toys = []
        price_tags = []

        for idx in keep:
            x1, y1, x2, y2 = map(int, boxes[idx].tolist())
            conf_score = scores[idx].item()
            cls_id = int(cls_ids[idx].item())
            name = self.names[cls_id]

            if name == "toy" and conf_score < 0.56: continue
            if name == "price-tag" and conf_score < 0.55: continue
            if name == "non-toy" and conf_score < 0.85: continue
            if y1 > h * 0.78 and name == "price-tag" and conf_score < 0.75: continue

            detection = {
                "bbox": [x1, y1, x2, y2],
                "confidence": round(conf_score, 4),
                "center": [(x1 + x2) // 2, (y1 + y2) // 2]
            }

            if name == "toy":
                toys.append(detection)
            elif name == "price-tag":
                price_tags.append(detection)

        return {"toys": toys, "price_tags": price_tags}

    def detect_json(self, image_path: str, conf: float = 0.35, iou: float = 0.42) -> str:
        result = self.detect(image_path, conf, iou)
        return json.dumps(result, indent=2, ensure_ascii=False)

    def detect_and_draw(self, image_path: str, output_path: str = None, conf: float = 0.35, iou: float = 0.42):
        """Виконує детекцію і зберігає фото з рамками"""
        result = self.detect(image_path, conf, iou)
        
        if output_path is None:
            output_path = str(Path(image_path).with_name("result_" + Path(image_path).name))

        # Завантажуємо оригінальне зображення
        img = cv2.imread(image_path)
        if img is None:
            print(f"❌ Не вдалося завантажити зображення: {image_path}")
            return result

        # Малюємо іграшки
        for det in result["toys"]:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
            label = f"toy {det['confidence']:.2f}"
            cv2.putText(img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0,255,0), 2)

        # Малюємо цінники
        for det in result["price_tags"]:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), 3)
            label = f"price {det['confidence']:.2f}"
            cv2.putText(img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0,165,255), 2)

        cv2.imwrite(output_path, img)
        print(f"✅ Збережено: {output_path}")
        print(f"   Іграшок: {len(result['toys'])} | Цінників: {len(result['price_tags'])}")
        return result


# ====================== ПРИКЛАД ВИКОРИСТАННЯ ======================
if __name__ == "__main__":
    detector = ToyEnsembleDetector(
        model10_path="models/best_v10.pt",
        model11_path="models/best_v11.pt"
    )
    
    image_path = "examples/photo_5404612431419479421_y (1).jpg"
    
    result = detector.detect(image_path)
    json_result = detector.detect_json(image_path)
    
    print(json_result)
    
    # Збереження фото з детекцією
    detector.detect_and_draw(image_path, output_path="result_with_boxes.jpg")
    
    # Збереження JSON
    with open("detection_result.json", "w", encoding="utf-8") as f:
        f.write(json_result)
