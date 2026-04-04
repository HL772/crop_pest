# 穹农智核：端云协同的多源融合病虫害诊断反馈与智能问答平台

> 英文名：`AgriOmniCore`

## 项目简介

穹农智核是一个面向农业病虫害诊断场景的端云协同平台，集成了多标签图像识别、知识库映射、策略检索与智能追问能力。

- `端`：本地模型完成病虫害图像推理（Top-5 候选 + 风险分级）
- `云`：通过 OpenAI 兼容接口获取结构化防治资料，并支持连续追问
- `协同`：Web 控制台与桌面 GUI 均可使用同一模型与知识库

## 核心能力

- 多源融合识别：融合病害与虫害标签体系（如 IP102 / Plant Pathology）
- 多标签诊断反馈：输出 Top-5 候选、置信度、风险等级与建议动作
- 智能问答工作台：按候选结果拉取策略摘要，并可继续追问
- 批量巡检：多图队列识别、失败重试、会话统计、CSV 导出
- 可视化看板：模型状态、诊断过程、风险仪表盘、会话分析

## 技术栈

- 后端：`FastAPI` + `PyTorch` + `timm`
- 前端：`HTML` + `CSS` + `Vanilla JS`
- 桌面端：`PyQt5`
- 推理与数据：`torchvision` / `Pillow` / `JSON` 知识库映射

## 目录结构

```text
.
├─ src/
│  ├─ web_service.py            # Web 后端服务（API + 静态资源）
│  ├─ model.py                  # 模型定义与模型加载
│  ├─ train.py                  # 训练脚本（多标签）
│  ├─ create_knowledge_base.py  # 生成/更新知识库映射
│  └─ gui_app.py                # 桌面版 GUI
├─ web/
│  ├─ index.html                # Web 页面
│  ├─ styles.css                # Web 样式
│  └─ app.js                    # Web 交互逻辑
├─ trained_models/              # 模型与标签映射、知识库
├─ sample_images/               # 示例图片
└─ readme.md
```

## 快速开始（Web 版）

### 1) 安装依赖

建议使用 Python 3.10+，并先创建虚拟环境。

```bash
pip install fastapi uvicorn torch torchvision timm pillow numpy pandas matplotlib seaborn scikit-learn tqdm
```

### 2) 启动服务

```bash
python src/web_service.py
```

浏览器访问：

```text
http://127.0.0.1:8000
```

### 3) 页面使用流程

1. 选择并加载模型（默认从 `trained_models/*.pth` 自动扫描）
2. 上传单张图片或从 `sample_images/` 选择示例
3. 点击识别查看 Top-5 候选与风险分析
4. 在策略工作台查询防治资料并继续追问
5. 批量模式可导出 CSV 结果

## 策略问答配置（云端）

服务支持 OpenAI 兼容接口，优先读取以下环境变量：

- `OPENAI_COMPAT_API_KEY`
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_MODEL`

PowerShell 示例：

```powershell
$env:OPENAI_COMPAT_API_KEY="your_api_key"
$env:OPENAI_COMPAT_BASE_URL="https://your-openai-compatible-endpoint/v1"
$env:OPENAI_COMPAT_MODEL="deepseek-chat"
python src/web_service.py
```

## 桌面版启动（PyQt）

```bash
pip install pyqt5
python src/gui_app.py
```

## 主要 API

- `GET /api/health`：健康状态、模型列表、策略服务状态
- `GET /api/models`：模型列表与当前模型信息
- `POST /api/models/load`：加载指定模型
- `GET /api/samples`：示例图片列表
- `POST /api/predict`：图片识别（请求体为二进制，需 `x-filename` 请求头）
- `POST /api/strategy`：策略整理与追问

## 训练与知识库更新

### 1) 模型训练

```bash
python src/train.py
```

说明：`src/train.py` 中 `CFG` 默认使用了本地绝对路径，实际训练前请按你的环境修改：

- `data_dir`
- `save_dir`
- `resume_from_checkpoint`（如不续训可置空）

### 2) 知识库生成

```bash
python src/create_knowledge_base.py
```

说明：脚本 `__main__` 中也包含默认绝对路径，需先改成你的项目路径后再运行。

## 注意事项

- `trained_models/` 目录下需同时具备模型权重与标签映射文件
- 若策略问答不可用，通常是 API Key / Base URL 未配置或网络不可达
- 识别结果为辅助决策信息，不替代现场农技诊断

## 作品名称

穹农智核：端云协同的多源融合病虫害诊断反馈与智能问答平台
