from __future__ import annotations

import io
import json
import logging
import os
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from torchvision import transforms

from model import load_model_with_labels


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "trained_models"
STATIC_DIR = BASE_DIR / "web"
SAMPLE_DIR = BASE_DIR / "sample_images"
DEEPSEEK_API_KEY = os.getenv(
    "DEEPSEEK_API_KEY",
    "sk-a2RcvEXRSsdkqhGXHOP9SpqrVsqr9InV0eSzMBcyPhqZexkI",
).strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/chat/completions",
).strip()
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
logger = logging.getLogger(__name__)


class InferenceService:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.idx_to_label: dict[str, str] = {}
        self.knowledge_base: dict[str, dict[str, Any]] = {}
        self.loaded_model_path = ""
        self.loaded_model_config: dict[str, Any] = {}

    def list_models(self) -> list[dict[str, str]]:
        if not MODEL_DIR.exists():
            return []

        models = sorted(MODEL_DIR.glob("*.pth"), key=lambda path: path.stat().st_mtime, reverse=True)
        return [{"name": model.name, "path": str(model)} for model in models]

    def list_samples(self) -> list[dict[str, str]]:
        if not SAMPLE_DIR.exists():
            return []

        images = []
        for image_path in sorted(SAMPLE_DIR.iterdir(), key=lambda path: path.name.lower()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            images.append(
                {
                    "name": image_path.name,
                    "url": f"/samples/{image_path.name}",
                }
            )
        return images

    def ensure_model_loaded(self) -> None:
        if self.model is not None:
            return

        models = self.list_models()
        if not models:
            raise RuntimeError("未在 trained_models 目录中找到可用的 .pth 模型文件。")

        self.load_model(models[0]["path"])

    def load_model(self, model_path: str) -> dict[str, Any]:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"模型文件不存在: {path}")

        model, _, idx_to_label, config = load_model_with_labels(str(path))
        knowledge_path = path.parent / "knowledge_base.json"
        if not knowledge_path.exists():
            raise FileNotFoundError(f"知识库文件不存在: {knowledge_path}")

        with knowledge_path.open("r", encoding="utf-8") as file:
            self.knowledge_base = json.load(file)

        self.model = model
        self.idx_to_label = idx_to_label
        self.loaded_model_path = str(path)
        self.loaded_model_config = config or {}

        return self.model_summary()

    def model_summary(self) -> dict[str, Any]:
        return {
            "loaded": self.model is not None,
            "model_path": self.loaded_model_path,
            "model_name": self.loaded_model_config.get("model_name", "未知"),
            "image_size": self.loaded_model_config.get("image_size", 224),
            "knowledge_base_count": len(self.knowledge_base),
            "device": str(self.device),
        }

    @staticmethod
    def risk_profile(confidence: float) -> dict[str, str]:
        if confidence >= 0.88:
            return {
                "level": "高可信",
                "tone": "high",
                "description": "建议优先按该结果进行人工复核。",
            }
        if confidence >= 0.68:
            return {
                "level": "需复核",
                "tone": "medium",
                "description": "建议结合田间症状与环境信息交叉确认。",
            }
        return {
            "level": "低确定性",
            "tone": "low",
            "description": "当前结果分散，建议查看更多候选并补充样本。",
        }

    def build_analysis(self, primary_result: dict[str, Any], filename: str) -> dict[str, Any]:
        confidence = primary_result["confidence"]
        readable_name = primary_result["readable_name"]
        dataset = primary_result["dataset"]

        if confidence >= 0.88:
            opening = f"模型高度怀疑该图像表现为“{readable_name}”。"
        elif confidence >= 0.68:
            opening = f"模型初步判断该图像更接近“{readable_name}”。"
        else:
            opening = f"模型暂未形成非常稳定的判断，当前更偏向“{readable_name}”。"

        return {
            "headline": f"诊断主结论: {readable_name}",
            "summary": (
                f"{opening} 当前样本文件为“{filename}”，该候选来自“{dataset}”标签集合。"
                " 单张图片识别仅可作为辅助判断，建议结合叶片、茎秆、果面等典型症状进一步确认。"
            ),
            "confidence_text": f"{confidence:.2%}",
            "risk_level": primary_result["risk_level"],
            "risk_tone": primary_result["risk_tone"],
            "next_actions": [
                "优先复核图像中最明显的病斑、虫咬痕迹或霉层区域。",
                "对照 Top-5 候选结果，确认是否存在相似病征或虫害混淆。",
                "如需处理建议，再点击候选卡片中的防治策略按钮查询资料。",
            ],
            "warning": "识别结果不能替代农技人员现场诊断或实验室检测。",
        }
    def predict(self, image_bytes: bytes, filename: str) -> dict[str, Any]:
        self.ensure_model_loaded()

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"无法读取上传图片: {exc}") from exc

        image_size = self.loaded_model_config.get("image_size", 224)
        transform = transforms.Compose(
            [
                transforms.Resize((image_size, image_size), antialias=True),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

        tensor = transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.sigmoid(logits)

        k = min(5, len(self.idx_to_label))
        topk_probs, topk_indices = torch.topk(probs.flatten(), k=k)

        results = []
        for rank in range(k):
            confidence = topk_probs[rank].item()
            idx_str = str(topk_indices[rank].item())
            kb_entry = self.knowledge_base.get(idx_str, {})
            risk = self.risk_profile(confidence)
            readable_name = kb_entry.get("readable_name", f"未知标签_{idx_str}")

            results.append(
                {
                    "rank": rank + 1,
                    "label_index": idx_str,
                    "original_label": self.idx_to_label.get(idx_str, f"unknown_{idx_str}"),
                    "readable_name": readable_name,
                    "dataset": kb_entry.get("dataset", "未知数据集"),
                    "confidence": confidence,
                    "confidence_text": f"{confidence:.2%}",
                    "risk_level": risk["level"],
                    "risk_tone": risk["tone"],
                    "risk_description": risk["description"],
                    "suggested_focus": f"建议优先核查“{readable_name}”相关的典型症状部位。",
                }
            )

        primary_result = results[0] if results else None
        analysis = self.build_analysis(primary_result, filename) if primary_result else {}

        return {
            "filename": filename,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "model": self.model_summary(),
            "primary_result": primary_result,
            "analysis": analysis,
            "results": results,
        }


def get_strategy_status() -> dict[str, str | bool]:
    if not DEEPSEEK_API_KEY:
        return {"available": False, "reason": "未配置 DeepSeek API Key。"}

    if not DEEPSEEK_API_KEY.startswith("sk-"):
        return {"available": False, "reason": "当前配置的 key 不是 DeepSeek 常见格式。"}

    if not DEEPSEEK_API_URL:
        return {"available": False, "reason": "未配置 DeepSeek API 地址。"}

    return {"available": True, "reason": "DeepSeek 资料整理可用。"}


def create_deepseek_payload(pest_name: str) -> dict[str, Any]:
    system_prompt = (
        "你是一名农业植保资料整理助手。"
        "请围绕用户提供的病虫害名称，输出结构化的中文资料摘要。"
        "不要编造精确药剂剂量、法规结论或最新政策。"
        "若信息不够确定，要明确提示仅供参考，需要结合当地农技建议。"
        "请严格输出 JSON 对象，包含 summary、items、sources 三个字段。"
        "items 是数组，每项包含 title、content、url。"
        "如果没有真实来源链接，url 置为空字符串。"
        "sources 是数组，每项包含 title、url。"
    )
    user_prompt = (
        f"请整理“{pest_name}”的相关资料，重点包括："
        "典型症状或危害表现、常见发生条件、田间处理思路、综合防治建议、使用提醒。"
        "输出要适合网页前端直接展示，语言简洁，不要使用 Markdown。"
    )
    return {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
        "stream": False,
    }


def format_deepseek_error(status_code: int, error_body: str) -> str:
    detail = error_body.strip()
    try:
        payload = json.loads(error_body)
    except json.JSONDecodeError:
        return f"DeepSeek 请求失败: HTTP {status_code} {detail or '未知错误'}"

    if isinstance(payload, dict):
        error_info = payload.get("error", payload)
        if isinstance(error_info, dict):
            detail = (
                str(error_info.get("message", "")).strip()
                or str(error_info.get("detail", "")).strip()
                or str(error_info.get("type", "")).strip()
                or detail
            )

    return f"DeepSeek 请求失败: HTTP {status_code} {detail or '未知错误'}"


def call_deepseek_for_strategy(pest_name: str) -> dict[str, Any]:
    payload = create_deepseek_payload(pest_name)
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(format_deepseek_error(exc.code, error_body)) from exc
    except Exception as exc:
        raise RuntimeError(f"DeepSeek 请求失败: {exc}") from exc

    try:
        response_data = json.loads(raw)
        content = response_data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"无法解析 DeepSeek 响应: {exc}") from exc

    try:
        structured = json.loads(content)
    except json.JSONDecodeError:
        structured = {
            "summary": "已生成相关资料摘要。",
            "items": [{"title": f"{pest_name} 资料摘要", "content": content, "url": ""}],
            "sources": [],
        }

    normalized_items = []
    for item in structured.get("items", []):
        normalized_items.append(
            {
                "title": str(item.get("title", "相关资料")),
                "content": str(item.get("content", "")),
                "url": str(item.get("url", "")),
            }
        )

    normalized_sources = []
    for source in structured.get("sources", []):
        normalized_sources.append(
            {
                "title": str(source.get("title", "参考资料")),
                "url": str(source.get("url", "")),
            }
        )

    return {
        "name": pest_name,
        "summary": str(structured.get("summary", f"已整理 {pest_name} 的相关资料。")),
        "items": normalized_items,
        "sources": normalized_sources,
    }
@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        service.ensure_model_loaded()
    except Exception:
        pass
    yield


service = InferenceService()
app = FastAPI(title="作物病虫害智能识别 Web 服务", version="2.0.0", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

if SAMPLE_DIR.exists():
    app.mount("/samples", StaticFiles(directory=SAMPLE_DIR), name="samples")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    strategy_status = get_strategy_status()
    return {
        "ok": True,
        "available_models": service.list_models(),
        "current_model": service.model_summary(),
        "strategy_available": strategy_status["available"],
        "strategy_status_reason": strategy_status["reason"],
        "sample_count": len(service.list_samples()),
    }


@app.get("/api/models")
def list_models() -> dict[str, Any]:
    return {
        "models": service.list_models(),
        "current_model": service.model_summary(),
    }


@app.get("/api/samples")
def list_samples() -> dict[str, Any]:
    return {"images": service.list_samples()}


@app.post("/api/models/load")
def load_model(payload: dict[str, str]) -> dict[str, Any]:
    model_path = payload.get("path", "").strip()
    if not model_path:
        raise HTTPException(status_code=400, detail="缺少模型路径。")

    try:
        current_model = service.load_model(model_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"message": "模型加载成功。", "current_model": current_model}


@app.post("/api/predict")
async def predict(request: Request) -> dict[str, Any]:
    filename = unquote(request.headers.get("x-filename", "").strip())
    if not filename:
        raise HTTPException(status_code=400, detail="缺少文件名，请通过 x-filename 请求头传递。")

    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空。")

    try:
        return service.predict(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/strategy")
def fetch_strategy(payload: dict[str, str]) -> dict[str, Any]:
    pest_name = payload.get("name", "").strip()
    if not pest_name:
        raise HTTPException(status_code=400, detail="缺少病虫害名称。")

    strategy_status = get_strategy_status()
    if not strategy_status["available"]:
        raise HTTPException(status_code=503, detail=str(strategy_status["reason"]))

    try:
        return call_deepseek_for_strategy(pest_name)
    except Exception as exc:
        logger.exception("Strategy lookup failed for %s", pest_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_service:app", host="127.0.0.1", port=8000, reload=False)

