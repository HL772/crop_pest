# 穹农智核：端云协同的多源融合病虫害诊断反馈与智能问答平台

> 英文名：`AgriOmniCore`

## 项目简介
穹农智核面向农业病虫害场景，提供“端侧图像诊断 + 云侧策略问答”的闭环能力。

- 端侧：本地模型进行病虫害识别，输出 Top-5 候选、置信度、风险分级
- 云侧：通过 OpenAI 兼容接口生成结构化防治资料并支持追问
- 协同：支持 Web 控制台与桌面 GUI 共用模型与知识库

## 核心能力
- 多源融合识别（病害 + 虫害标签体系）
- 诊断反馈（Top-5、风险等级、建议动作）
- 策略检索与智能问答（summary/items/sources）
- 批量巡检与 CSV 导出
- 会话统计与运行状态可视化

## 目录结构
```text
.
├─ src/
│  ├─ web_service.py
│  ├─ model.py
│  ├─ train.py
│  ├─ create_knowledge_base.py
│  └─ gui_app.py
├─ web/
│  ├─ index.html
│  ├─ styles.css
│  └─ app.js
├─ trained_models/
├─ sample_images/
├─ docs/
└─ readme.md
```

## 快速开始（Web）
1. 安装依赖：
```bash
pip install fastapi uvicorn torch torchvision timm pillow numpy pandas matplotlib seaborn scikit-learn tqdm pyqt5
```
2. 启动服务：
```bash
python src/web_service.py
```
3. 打开页面：`http://127.0.0.1:8000`

## 策略服务配置（可选）
```powershell
$env:OPENAI_COMPAT_API_KEY="your_api_key"
$env:OPENAI_COMPAT_BASE_URL="https://your-openai-compatible-endpoint/v1"
$env:OPENAI_COMPAT_MODEL="deepseek-chat"
```

## 桌面版（可选）
```bash
python src/gui_app.py
```

## 交付文档
- [01_交付清单](docs/01_交付清单.md)
- [02_部署与运行手册](docs/02_部署与运行手册.md)
- [03_API接口说明](docs/03_API接口说明.md)
- [04_模型与数据说明](docs/04_模型与数据说明.md)
- [05_测试与验收报告](docs/05_测试与验收报告.md)
- [06_已知问题与限制](docs/06_已知问题与限制.md)
- [07_演示脚本](docs/07_演示脚本.md)

## 说明
- 识别结果用于辅助判断，不替代农技现场诊断或实验室检测。
- 若未配置策略接口参数，系统可降级为“仅识别模式”。
