"""
贡柑病虫害检测 — 农户反馈模块
==============================
保存农户对识别结果的纠正反馈，用于后续数据清洗和模型再训练。

每条反馈保存为独立 JSON 文件 + 对应图片文件，
方便后续逐条审核和按需微调。

目录结构:
  feedback_data/
    ├── feedback_records.jsonl   # 所有反馈的汇总索引
    └── images/                  # 反馈对应的原始图片
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
FEEDBACK_DIR = BASE_DIR / "feedback_data"
IMAGES_DIR = FEEDBACK_DIR / "images"
INDEX_FILE = FEEDBACK_DIR / "feedback_records.jsonl"


def _ensure_dirs():
    """确保目录存在"""
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def save_feedback(image_file, model_result, correction, notes=""):
    """
    保存农户反馈。

    参数:
        image_file: Flask FileStorage 对象（原始图片）
        model_result: /predict 返回的完整结果 dict
        correction: 农户认为的真实病害（如 "黄龙病"）
        notes: 农户备注文字

    返回:
        {"ok": True, "feedback_id": "..."}
    """
    _ensure_dirs()

    feedback_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    # 保存图片
    ext = _get_ext(image_file.filename or "jpg")
    img_filename = f"{feedback_id}{ext}"
    img_path = IMAGES_DIR / img_filename
    image_file.seek(0)
    image_file.save(str(img_path))

    # 构建反馈记录
    record = {
        "feedback_id": feedback_id,
        "timestamp": datetime.now().isoformat(),
        "model_used": model_result.get("model_used", "unknown"),
        "original_prediction": {
            "class_name": model_result.get("class_name", ""),
            "class_id": model_result.get("class_id", -1),
            "confidence": model_result.get("confidence", 0),
        },
        "farmer_correction": correction,
        "image_file": img_filename,
        "notes": notes,
        "status": "pending_review",  # pending_review / confirmed / rejected
    }

    # 写入汇总索引（追加一行 JSONL，便于批量解析）
    with open(INDEX_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[反馈] {feedback_id}: 模型→{record['original_prediction']['class_name']}  农户→{correction}")

    return {"ok": True, "feedback_id": feedback_id}


def list_feedback(status=None):
    """读取所有反馈（可按状态筛选）"""
    _ensure_dirs()

    if not INDEX_FILE.exists():
        return []

    records = []
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if status is None or record.get("status") == status:
                records.append(record)

    return records


def get_feedback_summary():
    """返回反馈统计摘要"""
    records = list_feedback()
    total = len(records)
    correct = sum(1 for r in records if r["original_prediction"]["class_name"] == r["farmer_correction"])
    pending = sum(1 for r in records if r.get("status") == "pending_review")

    return {
        "total": total,
        "model_correct": correct,
        "model_wrong": total - correct,
        "pending_review": pending,
        "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
    }


def _get_ext(filename):
    """提取文件扩展名，不支持的类型回退到 .jpg"""
    _, ext = os.path.splitext(filename or ".jpg")
    ext = ext.lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp") else ".jpg"
