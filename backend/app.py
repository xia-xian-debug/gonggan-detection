"""
贡柑病虫害检测系统 — Flask 后端（多模型版）
==========================================
POST /predict   → 图片识别（可选 model 参数切换模型）
GET  /models    → 列出所有可用模型
GET  /diseases  → 病虫害百科
GET  /           → 前端页面
GET  /sw.js      → PWA Service Worker
"""

import json
import sys
from pathlib import Path

# 确保 backend 目录在 Python 路径中（无论从哪个目录启动）
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, render_template, request, jsonify, send_from_directory

from predict import get_manager, predict_image, list_models

app = Flask(__name__)

# ── 启动时加载 ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent

with open(BASE_DIR / "disease_info.json", "r", encoding="utf-8") as f:
    DISEASE_INFO = json.load(f)

# 初始化模型管理器
get_manager(str(PROJECT_DIR))


# ── 前端页面 ────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── PWA ─────────────────────────────────────────────────────
@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


# ── 🆕 模型列表接口（前端下拉菜单的数据来源） ─────────────────
@app.route("/models")
def api_list_models():
    """返回所有注册的模型及其信息"""
    return jsonify(list_models())


# ── 识别接口（支持多模型） ───────────────────────────────────
@app.route("/predict", methods=["POST"])
def predict():
    """
    接收图片 → 模型推理 → 合并病害百科 → 返回完整结果

    POST 参数:
        image: 图片文件（必传）
        model: 模型名称（可选，不传则用默认模型）
               可选值见 /models 接口返回的 name 字段
    """
    # 1. 校验图片
    if "image" not in request.files:
        return jsonify({"error": "未收到图片文件"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    # 2. 确定使用哪个模型
    model_name = request.form.get("model", None)  # None = 用默认模型（ACTIVE_MODEL）

    # 3. 模型推理
    try:
        result = predict_image(file, model_name=model_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"模型推理失败: {str(e)}"}), 500

    # 4. 合并病害百科信息（自动去除"（叶片）""（果实）"后缀匹配）
    disease_name = result["class_name"]
    base_name = disease_name.replace("（叶片）", "").replace("（果实）", "")
    info = DISEASE_INFO.get(base_name, {})
    if info:
        result.update({
            "severity":    info["severity"],
            "description": info["description"],
            "symptoms":    info["symptoms"],
            "treatment":   info["treatment"],
            "pesticides":  info["pesticides"],
        })

    # 附上实际使用的模型名
    result["model_used"] = model_name or "mixed"

    return jsonify(result)


# ── 病虫害百科接口 ────────────────────────────────────────────
@app.route("/diseases")
def api_list_diseases():
    return jsonify(DISEASE_INFO)


# ── 启动 ────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, socket

    # Render / 云服务器用 gunicorn，不走这里
    port = int(os.environ.get("PORT", 5000))

    # 本地开发：自动开 ngrok 公网隧道（手机跨网络访问用）
    # 需要先注册 ngrok 并获取 authtoken → 设为环境变量 NGROK_AUTHTOKEN
    NGROK_TOKEN = os.environ.get("NGROK_AUTHTOKEN", "")
    public_url = None

    if NGROK_TOKEN:
        try:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = NGROK_TOKEN
            tunnel = ngrok.connect(port, "http")
            public_url = tunnel.public_url
        except Exception as e:
            print(f"  [警告] ngrok 启动失败: {e}")

    local_ip = socket.gethostbyname(socket.gethostname())
    available = [f'{k} ({v["description"]})' for k, v in __import__("predict").MODEL_REGISTRY.items()]

    print("\n" + "=" * 56)
    print("  贡柑病虫害检测系统 — 服务已启动")
    print("=" * 56)
    print(f"  本机访问:    http://127.0.0.1:{port}")
    print(f"  局域网访问:  http://{local_ip}:{port}")
    if public_url:
        print(f"  >> 公网访问:  {public_url}")
    print(f"  可用模型:    {', '.join(available)}")
    print("=" * 56)
    if public_url:
        print("  手机在任意网络下打开「公网访问」链接即可使用")
    print()

    app.run(debug=False, host="0.0.0.0", port=port)
