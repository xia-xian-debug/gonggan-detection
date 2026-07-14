"""
贡柑病虫害检测 — 数据准备模块
==============================
扫描 Kaggle 柑橘数据集文件夹，生成 labels.csv

用法:
  python prepare.py --data_dir ../data/kaggle

数据集文件夹结构（Kaggle Citrus Leaves 下载后解压即可）:
  data/kaggle/
    ├── Black spot/    (或 Black_spot)
    ├── Canker/
    ├── Greening/      → 映射为 "黄龙病"
    ├── Healthy/
    └── Anthracnose/   (如有；没有则用 Melanose 或单独收集)
"""

import argparse
import csv
import os
import sys
from collections import Counter
from pathlib import Path

# ── 类别映射 ──────────────────────────────────────────────
# Kaggle 文件夹名 → 中文病害名（用于显示）
CATEGORY_MAP = {
    "greening":       "黄龙病",
    "hlb":            "黄龙病",
    "huanglongbing":  "黄龙病",
    "canker":         "溃疡病",
    "citrus_canker":  "溃疡病",
    "black_spot":     "黑星病",
    "black spot":     "黑星病",
    "anthracnose":    "炭疽病",
    "healthy":        "健康",
    "health":         "健康",
    "melanose":       "黑星病",   # 类似黑星病，可归入此类
}

# 类别名 → 数字标签
LABEL_MAP = {
    "黄龙病": 0,
    "溃疡病": 1,
    "黑星病": 2,
    "炭疽病": 3,
    "健康":   4,
}

# 支持的图片格式
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def classify_folder(folder_name: str) -> str | None:
    """根据文件夹名判断病害类别。"""
    name = folder_name.strip().lower().replace("_", " ")
    for key, chinese in CATEGORY_MAP.items():
        if key in name:
            return chinese
    return None


def scan_dataset(data_dir: str, output_csv: str = None):
    """扫描数据集文件夹，生成 labels.csv。"""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"[错误] 数据目录不存在: {data_path}")
        sys.exit(1)

    if output_csv is None:
        output_csv = str(Path(__file__).resolve().parent.parent / "data" / "labels.csv")
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("步骤 1/4：扫描数据集 & 生成 labels.csv")
    print("=" * 60)

    # 遍历子文件夹
    rows = []
    unmatched_folders = set()
    category_counts = Counter()

    for subdir in sorted(data_path.iterdir()):
        if not subdir.is_dir():
            continue

        folder_name = subdir.name
        category = classify_folder(folder_name)

        if category is None:
            unmatched_folders.add(folder_name)
            continue

        # 收集该文件夹下所有图片
        images = []
        for ext in IMAGE_EXTS:
            images.extend(subdir.glob(f"*{ext}"))
            images.extend(subdir.glob(f"*{ext.upper()}"))

        for img_path in images:
            rows.append({
                "image_path": str(img_path),
                "label": LABEL_MAP[category],
                "category": category,
            })
            category_counts[category] += 1

        print(f"  {folder_name} → {category}: {len(images)} 张")

    # 写入 labels.csv
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "label", "category"])
        writer.writeheader()
        writer.writerows(rows)

    # ── 统计报告 ──
    print(f"\n写入 {len(rows)} 条记录 → {output_path}")

    if unmatched_folders:
        print(f"\n[警告] 未识别的文件夹（可手动加入 CATEGORY_MAP）:")
        for f in unmatched_folders:
            print(f"  - {f}")

    print("\n各类别统计:")
    for cat in LABEL_MAP:
        count = category_counts.get(cat, 0)
        pct = count / len(rows) * 100 if rows else 0
        print(f"  {LABEL_MAP[cat]} ({cat}): {count} 张 ({pct:.1f}%)")
    print(f"  合计: {len(rows)} 张")

    # 检查：如果某类为 0 张，给出警告
    missing = [cat for cat, label in LABEL_MAP.items() if category_counts.get(cat, 0) == 0]
    if missing:
        print(f"\n[警告] 以下类别没有图片: {missing}")
        print("  → 请检查数据集文件夹，或修改 CATEGORY_MAP")
        print("  → 如果确实缺少某类，训练时会跳过该类")

    return rows


def main():
    parser = argparse.ArgumentParser(
        description="扫描 Kaggle 柑橘病害数据集 → 生成 labels.csv")
    parser.add_argument("--data_dir", required=True,
                        help="数据集根目录（包含 Black spot/, Canker/, 等子文件夹）")
    parser.add_argument("--output", default=None,
                        help="输出 CSV 路径（默认: data/labels.csv）")
    args = parser.parse_args()
    scan_dataset(args.data_dir, args.output)


if __name__ == "__main__":
    main()
