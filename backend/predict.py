"""
贡柑病虫害检测 — 模型预测模块（多模型版）
==========================================
支持同时加载多个模型，通过 MODEL_REGISTRY 集中管理。

换模型只需改第 35 行的 ACTIVE_MODEL 变量，或让前端传 model 参数。

用法:
  from predict import predict_image
  result = predict_image(img, model="mixed")   # 指定模型
  result = predict_image(img)                  # 使用默认模型
"""

import io
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torchvision
from torchvision import transforms
from PIL import Image, UnidentifiedImageError

import torch.serialization
torch.serialization.add_safe_globals([nn.Parameter, nn.Module, dict, list])


# ═══════════════════════════════════════════════════════════
# 📋 模型注册表 —— 所有模型在这里登记，换模型只改这里
# ═══════════════════════════════════════════════════════════
#
# 每个条目：
#   path        → .pth 文件路径（相对于项目根目录）
#   arch        → 模型架构：mobilenet_v3_large / mobilenet_v3_small
#   num_classes → 输出类别数
#   labels      → 类别 ID → 中文名 映射
#   description → 用途说明

MODEL_REGISTRY = {

    # ── 版本 2：叶片+果实混合模型 ──
    "mixed": {
        "path": "mobilenetv3_best_new_leaves_and_fruit.pth",
        "arch": "mobilenet_v3_large",
        "num_classes": 14,
        "labels": {
            0:  "柑橘虫害（叶片）",
            1:  "柑橘结痂（叶片）",
            2:  "柑橘溃疡病（叶片）",
            3:  "柑橘煤烟病（叶片）",
            4:  "柑橘叶矿蛾（叶片）",
            5:  "柑橘印度教螨（叶片）",
            6:  "黑斑病（叶片）",
            7:  "黄龙病（叶片）",
            8:  "健康（叶片）",
            9:  "柑橘结痂（果实）",
            10: "柑橘溃疡病（果实）",
            11: "黑斑病（果实）",
            12: "黄龙病（果实）",
            13: "健康（果实）",
        },
        "description": "叶片+果实混合训练（14 分类）",
    },

    # ── 版本 1a：叶片专用模型 ──
    "leaf": {
        "path":        "mobilenetv3_best_new.pth",
        "arch":        "mobilenet_v3_large",
        "num_classes": 9,
        "labels": {
            0: "柑橘虫害",
            1: "柑橘结痂",
            2: "柑橘溃疡病",
            3: "柑橘煤烟病",
            4: "柑橘叶矿蛾",
            5: "柑橘印度教螨",
            6: "黑斑病",
            7: "黄龙病",
            8: "健康",
        },
        "description": "叶片专用（9 分类）",
    },

    # ── 版本 1b：果实专用模型 ──
    "fruit": {
        "path":        "mobilenetv3_best_new_fruit.pth",
        "arch":        "mobilenet_v3_large",
        "num_classes": 5,
        "labels":      {0: "柑橘结痂", 1: "柑橘溃疡病", 2: "黑斑病", 3: "黄龙病", 4: "健康"},
        "description": "果实专用（5 分类）",
    },
}

# ← 当前使用的模型，改成 "leaf" 或 "fruit" 即可切换
ACTIVE_MODEL = "mixed"


# ═══════════════════════════════════════════════════════════
# 图像预处理（所有模型共用）
# ═══════════════════════════════════════════════════════════
MODEL_INPUT_SIZE = 224

TRANSFORM = transforms.Compose([
    transforms.Resize((MODEL_INPUT_SIZE, MODEL_INPUT_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

MAX_PRE_RESIZE = 1024


# ═══════════════════════════════════════════════════════════
# 模型构建工厂
# ═══════════════════════════════════════════════════════════

def _build_model(arch: str, num_classes: int) -> nn.Module:
    """根据架构名自动构建模型骨架。

    支持的架构（可随时添加新的）：
    - mobilenet_v3_small
    - mobilenet_v3_large
    """
    arch_map = {
        "mobilenet_v3_small": torchvision.models.mobilenet_v3_small,
        "mobilenet_v3_large": torchvision.models.mobilenet_v3_large,
    }

    if arch not in arch_map:
        raise ValueError(
            f"不支持的架构: {arch}。可选: {list(arch_map.keys())}"
        )

    model = arch_map[arch](weights=None)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    print(f"  [模型骨架] {arch}，输出 {num_classes} 类")
    return model


# ═══════════════════════════════════════════════════════════
# 预测器类
# ═══════════════════════════════════════════════════════════

class CitrusPredictor:
    """单个模型的预测器。

    参数:
        model_config: MODEL_REGISTRY 中的一个条目
        model_dir: 项目根目录（用于拼接 .pth 路径）
        device: "cuda" / "cpu"
    """

    def __init__(self, model_config: dict, model_dir: str, device: str = "cpu"):
        self.config = model_config
        self.labels = model_config["labels"]
        self.description = model_config.get("description", "")
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")

        model_path = str(Path(model_dir) / model_config["path"])
        self.model = self._load_model(
            model_path,
            arch=model_config["arch"],
            num_classes=model_config["num_classes"],
        )
        self.model.to(self.device)
        self.model.eval()
        print(f"  [加载完成] {model_config.get('description', model_path)}，设备: {self.device}")

    def _load_model(self, model_path: str, arch: str, num_classes: int) -> nn.Module:
        """智能加载 .pth：自动识别完整模型 / state_dict / checkpoint dict。"""
        checkpoint = torch.load(
            model_path,
            map_location=self.device,
            weights_only=False,
        )

        # 情况 1：torch.save(model, ...) — 完整模型直接能用
        if isinstance(checkpoint, nn.Module):
            print("  [检测] 完整模型，直接加载")
            return checkpoint

        # 情况 2：单纯的 state_dict — 需要重建架构
        if isinstance(checkpoint, dict):
            # 如果 dict 里有 model_state_dict / state_dict 键，取出来
            if "model_state_dict" in checkpoint:
                state = checkpoint["model_state_dict"]
            elif "state_dict" in checkpoint:
                state = checkpoint["state_dict"]
            else:
                state = checkpoint

            print(f"  [检测] state_dict，重建 {arch} 架构")
            model = _build_model(arch, num_classes)
            model.load_state_dict(state, strict=False)
            return model

        raise TypeError(f"无法识别的 .pth 文件格式: {type(checkpoint)}")

    def predict(self, image_input) -> dict:
        # ── 第1步：打开图片 ──
        image = self._open_image(image_input)
        # ── 第2步：校验 ──
        self._validate_image(image)
        # ── 第3步：预缩放 ──
        image = self._pre_resize(image)
        # ── 第4步：推理 ──
        tensor = TRANSFORM(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=-1)

        predicted_class = int(probs.argmax(dim=-1).item())
        confidence = float(probs.max().item())

        return {
            "class_id":   predicted_class,
            "class_name": self.labels[predicted_class],
            "confidence": round(confidence, 4),
            "probs":      [round(float(p), 4) for p in probs.squeeze(0)],
        }

    # ── 图片处理方法（与前版相同，略） ──
    @staticmethod
    def _open_image(source):
        try:
            if isinstance(source, (str, Path)):
                img = Image.open(source)
            elif isinstance(source, Image.Image):
                img = source
            elif isinstance(source, bytes):
                img = Image.open(io.BytesIO(source))
            elif hasattr(source, "read"):
                img = Image.open(io.BytesIO(source.read()))
            elif hasattr(source, "stream"):
                img = Image.open(source.stream)
            else:
                raise TypeError(f"不支持的输入类型: {type(source).__name__}")
            return CitrusPredictor._to_rgb(img)
        except UnidentifiedImageError:
            raise ValueError("无法识别该图片格式，请确认上传的是有效的图片文件。")
        except OSError as e:
            raise ValueError(f"图片文件读取失败（可能已损坏）: {e}")

    @staticmethod
    def _to_rgb(img: Image.Image) -> Image.Image:
        mode = img.mode
        if mode == "RGB":
            return img
        if mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            return bg
        if mode == "P":
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            return bg
        return img.convert("RGB")

    @staticmethod
    def _validate_image(img: Image.Image):
        w, h = img.size
        if w < 32 or h < 32:
            raise ValueError(f"图片尺寸过小 ({w}×{h})，请上传至少 32×32 像素的清晰照片。")

    @staticmethod
    def _pre_resize(img: Image.Image) -> Image.Image:
        w, h = img.size
        max_dim = max(w, h)
        if max_dim <= MAX_PRE_RESIZE:
            return img
        ratio = MAX_PRE_RESIZE / max_dim
        return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)


# ═══════════════════════════════════════════════════════════
# 模型管理器 —— 加载+缓存多个模型
# ═══════════════════════════════════════════════════════════

class ModelManager:
    """管理多个预测器，按需加载，全局缓存。

    用法:
        mgr = ModelManager("/path/to/project")
        result = mgr.predict("mixed", image)   # 指定模型
        result = mgr.predict(None, image)      # 用默认模型（ACTIVE_MODEL）
        print(mgr.list_models())               # 列出所有可用模型
    """

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self._predictors = {}  # dict[str, CitrusPredictor]

    def get(self, model_name: str) -> CitrusPredictor:
        """获取指定模型（未加载则先加载并缓存）"""
        if model_name not in self._predictors:
            config = MODEL_REGISTRY.get(model_name)
            if config is None:
                available = list(MODEL_REGISTRY.keys())
                raise ValueError(f"未知模型: {model_name}。可用: {available}")
            print(f"\n[ModelManager] 加载模型: {model_name} — {config.get('description', '')}")
            self._predictors[model_name] = CitrusPredictor(
                config, self.project_dir
            )
        return self._predictors[model_name]

    def predict(self, model_name, image_input) -> dict:  # model_name: Optional[str]
        """预测，model_name 为 None 时使用默认模型"""
        name = model_name or ACTIVE_MODEL
        return self.get(name).predict(image_input)

    def list_models(self):  # -> list[dict]
        """列出注册表中所有模型的信息"""
        return [
            {
                "name": name,
                "description": cfg["description"],
                "num_classes": cfg["num_classes"],
                "labels": list(cfg["labels"].values()),
                "loaded": name in self._predictors,
            }
            for name, cfg in MODEL_REGISTRY.items()
        ]


# ═══════════════════════════════════════════════════════════
# 全局单例（app.py 启动时初始化一次）
# ═══════════════════════════════════════════════════════════

_manager = None  # Optional[ModelManager]


def get_manager(project_dir: str = ".") -> ModelManager:
    global _manager
    if _manager is None:
        _manager = ModelManager(project_dir)
    return _manager


def predict_image(image_input, model_name=None) -> dict:  # model_name: Optional[str]
    """供 Flask 调用的快捷函数。model_name=None 时使用 ACTIVE_MODEL"""
    return get_manager().predict(model_name, image_input)


def list_models():  # -> list[dict]
    """返回所有可用模型列表（供前端下拉菜单）"""
    return get_manager().list_models()
