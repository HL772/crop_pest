# API 接口说明

## 1. 基本信息
- 服务基址：`http://127.0.0.1:8000`
- 数据格式：JSON（`/api/predict` 请求体为图片二进制）

## 2. 接口列表

### 2.1 健康检查
- 方法：`GET /api/health`
- 说明：查看服务状态、可用模型、策略服务可用性

示例响应：
```json
{
  "ok": true,
  "available_models": [{"name": "best_model_f1.pth", "path": "..."}],
  "current_model": {"loaded": true, "model_name": "tf_efficientnet_b5.ns_jft_in1k"},
  "strategy_available": true,
  "strategy_status_reason": "OpenAI 兼容策略服务可用。",
  "sample_count": 10
}
```

### 2.2 模型列表
- 方法：`GET /api/models`
- 说明：列出模型并返回当前模型摘要

### 2.3 加载模型
- 方法：`POST /api/models/load`
- 请求体：
```json
{"path":"D:/.../trained_models/best_model_f1.pth"}
```

### 2.4 示例图库
- 方法：`GET /api/samples`
- 说明：返回 `sample_images/` 下可展示图片

### 2.5 图片识别
- 方法：`POST /api/predict`
- Header：
  - `Content-Type: application/octet-stream`
  - `x-filename: <url-encoded-filename>`
- Body：图片二进制

示例响应（节选）：
```json
{
  "filename": "leaf.jpg",
  "generated_at": "2026-04-09T10:00:00",
  "primary_result": {
    "rank": 1,
    "readable_name": "白粉病（Powdery Mildew）",
    "confidence": 0.91,
    "confidence_text": "91.00%",
    "risk_level": "高可信"
  },
  "results": []
}
```

### 2.6 策略查询与追问
- 方法：`POST /api/strategy`

首轮请求：
```json
{"name":"白粉病（Powdery Mildew）"}
```

追问请求：
```json
{
  "name":"白粉病（Powdery Mildew）",
  "question":"连续阴雨条件下如何调整处理节奏？",
  "context":"已有摘要",
  "history":[{"role":"user","content":"..."}]
}
```

响应字段：`summary`、`items[]`、`sources[]`

## 3. 错误码约定
- `400`：参数缺失或格式错误
- `500`：推理/服务内部错误
- `503`：策略服务不可用（未配置或不可达）
