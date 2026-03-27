# gui_app.py (v3.7 - DeepSeek 策略查询版)
"""
图形用户界面（GUI）应用程序 - v3.7 DeepSeek 策略查询版
功能：
- [核心修正] 防治策略查询改为调用 DeepSeek，不再依赖 Tavily 和翻译中转。
- [优化] 直接输出中文结构化资料，减少额外处理步骤。
- [集成] 已将用户提供的 DeepSeek API 密钥接入策略查询流程。
- 集成知识库(knowledge_base.json)，将模型输出的内部标签实时转换为用户可读的病虫害名称。
"""
import sys
import os
import time
import json
import urllib.error
import urllib.request
from pathlib import Path
import traceback
from functools import partial

from PIL import Image

try:
    from PIL.ImageQt import ImageQt
except ImportError:
    ImageQt = None

import numpy as np
import torch
from torchvision import transforms

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QPixmap, QFont, QColor)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QTextEdit, QProgressBar, QFrame, QScrollArea,
    QGroupBox, QSplitter, QComboBox, QMessageBox,
    QGraphicsDropShadowEffect)

# ======================= DeepSeek 策略查询集成 =======================
DEEPSEEK_API_KEY = os.getenv(
    "DEEPSEEK_API_KEY",
    "sk-a2RcvEXRSsdkqhGXHOP9SpqrVsqr9InV0eSzMBcyPhqZexkI",
).strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/chat/completions",
).strip()


def get_strategy_status():
    if not DEEPSEEK_API_KEY:
        return False, "未配置 DeepSeek API Key。"
    if not DEEPSEEK_API_KEY.startswith("sk-"):
        return False, "当前配置的 key 不是 DeepSeek 常见格式。"
    if not DEEPSEEK_API_URL:
        return False, "未配置 DeepSeek API 地址。"
    return True, "DeepSeek 资料整理可用。"


STRATEGY_ENABLED, STRATEGY_STATUS = get_strategy_status()


def create_deepseek_payload(pest_name):
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
        "输出要适合桌面端直接展示，语言简洁，不要使用 Markdown。"
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


def fetch_strategy_with_deepseek(pest_name):
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
        raise RuntimeError(f"DeepSeek 请求失败: HTTP {exc.code} {error_body}") from exc
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
            "summary": f"已整理 {pest_name} 的相关资料。",
            "items": [{"title": f"{pest_name} 资料摘要", "content": content, "url": ""}],
            "sources": [],
        }

    items = []
    for item in structured.get("items", []):
        items.append(
            {
                "title": str(item.get("title", "相关资料")),
                "content": str(item.get("content", "")),
                "url": str(item.get("url", "")),
            }
        )

    sources = []
    for source in structured.get("sources", []):
        sources.append(
            {
                "title": str(source.get("title", "参考资料")),
                "url": str(source.get("url", "")),
            }
        )

    return {
        "summary": str(structured.get("summary", f"已整理 {pest_name} 的相关资料。")),
        "items": items,
        "sources": sources,
    }
# ===================================================================

from model import load_model_with_labels


# =========================== 自定义控件 ========================= #
class ModernButton(QPushButton):
    def __init__(self, text, primary: bool = False):
        super().__init__(text)
        self.primary = primary
        self.setFixedHeight(45)
        self.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self.get_style())

    def get_style(self):
        if self.primary:
            return """
                QPushButton {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4CAF50, stop:1 #45a049);color:#fff;border:none;border-radius:22px;padding:10px 20px;}
                QPushButton:hover {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #5CBF60, stop:1 #55b059);}
                QPushButton:pressed {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3CAF40, stop:1 #35a039);}
                QPushButton:disabled{background:#ccc;color:#666;}
            """
        else:
            return """
                QPushButton {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f8f9fa, stop:1 #e9ecef);color:#495057;border:2px solid #dee2e6;border-radius:22px;padding:10px 20px;}
                QPushButton:hover {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e9ecef, stop:1 #dee2e6);border-color:#adb5bd;}
                QPushButton:pressed {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #dee2e6, stop:1 #ced4da);}
                QPushButton:disabled{background:#ccc;color:#666;border-color:#bbb;}
            """


class ResultCard(QFrame):
    def __init__(self, readable_name: str, confidence: float, rank: int, on_strategy_click):
        super().__init__()
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        self.setMinimumHeight(80)
        base = QHBoxLayout(self)
        base.setContentsMargins(15, 10, 15, 10)

        lbl_rank = QLabel(f"#{rank}")
        lbl_rank.setAlignment(Qt.AlignCenter)
        lbl_rank.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        lbl_rank.setFixedSize(40, 40)
        rank_style = "color:{color};background:{bg};border:1px solid {color};border-radius:20px;"
        if rank == 1:
            lbl_rank.setStyleSheet(rank_style.format(color="#FFD700", bg="#FFF8DC"))
        elif rank == 2:
            lbl_rank.setStyleSheet(rank_style.format(color="#C0C0C0", bg="#F5F5F5"))
        elif rank == 3:
            lbl_rank.setStyleSheet(rank_style.format(color="#CD7F32", bg="#FDF5E6"))
        else:
            lbl_rank.setStyleSheet(rank_style.format(color="#666", bg="#f8f9fa"))

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        lbl_cls = QLabel(readable_name)
        lbl_cls.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        lbl_cls.setWordWrap(True)

        lbl_conf = QLabel(f"置信度: {confidence:.2%}")
        lbl_conf.setFont(QFont("Microsoft YaHei", 9))
        lbl_conf.setStyleSheet("color:#666;")

        info_layout.addWidget(lbl_cls)
        info_layout.addWidget(lbl_conf)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(confidence * 100))
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        color = "#4CAF50" if confidence > 0.8 else "#FFC107" if confidence > 0.6 else "#F44336"
        bar.setStyleSheet(
            f"QProgressBar{{border:none;border-radius:4px;background:#e0e0e0;}} QProgressBar::chunk{{background:{color};border-radius:4px;}}")

        v_bar_layout = QVBoxLayout()
        v_bar_layout.addWidget(bar)

        btn_strategy = QPushButton("获取防治策略")
        btn_strategy.setFont(QFont("Microsoft YaHei", 9))
        btn_strategy.setCursor(Qt.PointingHandCursor)
        btn_strategy.setStyleSheet(
            "QPushButton {background:#e7f3ff; color:#0056b3; border:1px solid #b8d6fb; border-radius:12px; padding: 5px 10px;} QPushButton:hover {background:#d0e7ff;}")
        btn_strategy.clicked.connect(on_strategy_click)
        if not STRATEGY_ENABLED:
            btn_strategy.setEnabled(False)
            btn_strategy.setText("策略查询不可用")

        base.addWidget(lbl_rank)
        base.addSpacing(10)
        base.addLayout(info_layout, 2)
        base.addLayout(v_bar_layout, 1)
        base.addWidget(btn_strategy)

        self.setStyleSheet(
            "QFrame{background:#fff;border:1px solid #e0e0e0;border-radius:10px;margin:5px;} QFrame:hover{border-color:#4CAF50;}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)


# ============================= 主界面 ============================ #
class CropDiseaseClassifierGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.idx_to_label = None, {}
        self.knowledge_base = {}
        self.loaded_model_name, self.current_image_path = "未知", ""
        self.loaded_model_config = {}
        self._init_ui()
        self._scan_models()

    def _init_ui(self):
        self.setWindowTitle("作物病虫害智能识别与防治系统 v3.7 (DeepSeek策略查询版)");
        self.setMinimumSize(1200, 800)
        central = QWidget(self);
        self.setCentralWidget(central)
        main = QHBoxLayout(central);
        splitter = QSplitter(Qt.Horizontal);
        main.addWidget(splitter)
        left = QWidget();
        left_layout = QVBoxLayout(left);
        splitter.addWidget(left)

        grp_model = QGroupBox("1. 模型选择");
        v_model = QVBoxLayout(grp_model)
        self.model_combo = QComboBox();
        self.model_combo.addItem("请从列表中选择或浏览本地模型…")
        self.btn_browse_model = ModernButton("浏览模型文件");
        self.btn_load_model = ModernButton("加载选中模型", primary=True);
        self.lbl_model_state = QLabel("模型状态: 未加载");
        self.lbl_model_state.setStyleSheet("color:red;font-weight:bold;padding:5px;")
        v_model.addWidget(self.model_combo);
        v_model.addWidget(self.btn_browse_model);
        v_model.addWidget(self.btn_load_model)

        grp_img = QGroupBox("2. 图像识别");
        v_img = QVBoxLayout(grp_img)
        self.image_label = QLabel("请先加载模型，然后选择图像");
        self.image_label.setMinimumSize(400, 400);
        self.image_label.setAlignment(Qt.AlignCenter);
        self.image_label.setWordWrap(True)
        self.image_label.setStyleSheet(
            "QLabel{border:3px dashed #dee2e6;border-radius:15px;background:#f8f9fa;color:#6c757d;font-size:14px;}")
        h_btns = QHBoxLayout()
        self.btn_select_image = ModernButton("选择图像", primary=True)
        self.btn_predict = ModernButton("开始识别")
        h_btns.addWidget(self.btn_select_image);
        h_btns.addWidget(self.btn_predict)
        v_img.addWidget(self.image_label);
        v_img.addLayout(h_btns)

        grp_info = QGroupBox("模型信息");
        v_info = QVBoxLayout(grp_info)
        self.txt_model_info = QTextEdit("请先选择并加载模型…");
        self.txt_model_info.setReadOnly(True)
        v_info.addWidget(self.txt_model_info)
        left_layout.addWidget(grp_model);
        left_layout.addWidget(self.lbl_model_state);
        left_layout.addWidget(grp_img);
        left_layout.addWidget(grp_info)

        right = QWidget();
        right_layout = QVBoxLayout(right);
        splitter.addWidget(right)
        grp_res = QGroupBox("识别结果");
        v_res = QVBoxLayout(grp_res)
        scroll = QScrollArea();
        scroll.setWidgetResizable(True);
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.result_container = QWidget();
        self.result_layout = QVBoxLayout(self.result_container);
        self.result_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.result_container);
        v_res.addWidget(scroll)

        grp_detail = QGroupBox("详细信息与防治策略");
        v_detail = QVBoxLayout(grp_detail)
        self.txt_detail = QTextEdit();
        self.txt_detail.setReadOnly(True);
        self.txt_detail.setFont(QFont("Microsoft YaHei", 10))
        self.txt_detail.setMinimumHeight(220)
        v_detail.addWidget(self.txt_detail)
        right_layout.addWidget(grp_res);
        right_layout.addWidget(grp_detail)

        self.statusBar().showMessage("就绪 - 请先加载模型")
        splitter.setSizes([600, 800])

        self.btn_browse_model.clicked.connect(self._browse_model)
        self.btn_load_model.clicked.connect(self._load_selected_model)
        self.btn_select_image.clicked.connect(self._select_image)
        self.btn_predict.clicked.connect(self._predict)

        self.btn_load_model.setEnabled(False)
        self.btn_select_image.setEnabled(False)
        self.btn_predict.setEnabled(False)

        if not STRATEGY_ENABLED:
            self.statusBar().showMessage(f"警告：防治策略查询当前不可用。{STRATEGY_STATUS}")

    def _scan_models(self):
        model_dir = Path(__file__).resolve().parent.parent / "trained_models"
        self.model_combo.clear()
        self.model_combo.addItem("请从列表中选择或浏览本地模型…")
        if model_dir.is_dir():
            pths = sorted([p for p in model_dir.glob("*.pth")], key=os.path.getmtime, reverse=True)
            for p in pths:
                self.model_combo.addItem(p.name, str(p))
        if self.model_combo.count() > 1:
            self.btn_load_model.setEnabled(True)

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型文件",
                                              str(Path(__file__).resolve().parent.parent / "trained_models"),
                                              "PyTorch模型 (*.pth)")
        if path:
            self.model_combo.addItem(Path(path).name, path)
            self.model_combo.setCurrentText(Path(path).name)
            self.btn_load_model.setEnabled(True)

    def _load_selected_model(self):
        path = self.model_combo.currentData()
        if not path: return
        try:
            self.model, _, self.idx_to_label, self.loaded_model_config = load_model_with_labels(path)

            knowledge_path = Path(path).parent / "knowledge_base.json"
            if not knowledge_path.exists():
                QMessageBox.critical(self, "错误",
                                     f"知识库文件 'knowledge_base.json' 未找到！\n请确保它与模型文件在同一目录下。")
                return

            with open(knowledge_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)

            model_name = self.loaded_model_config.get('model_name', '未知')
            self.lbl_model_state.setText(f"模型已加载: {model_name}")
            self.lbl_model_state.setStyleSheet("color:green;font-weight:bold;")
            self.btn_select_image.setEnabled(True)
            self.txt_model_info.setText(f"模型名称: {model_name}\n"
                                        f"知识库类别: {len(self.knowledge_base)}\n"
                                        f"图片尺寸: {self.loaded_model_config.get('image_size', '未知')}")
            self._clear_results()
            self.txt_detail.setText("模型和知识库加载成功，请选择图片进行识别。")

        except Exception:
            QMessageBox.critical(self, "错误", f"模型加载失败:\n{traceback.format_exc()}")
            self.lbl_model_state.setText("加载失败");
            self.lbl_model_state.setStyleSheet("color:red;font-weight:bold;")

    def _select_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择图像文件", "", "图片文件 (*.jpg *.jpeg *.png)")
        if path:
            self.current_image_path = path
            self._show_image(path)
            self._clear_results()
            self.btn_predict.setEnabled(True)

    def _show_image(self, path):
        try:
            pixmap = QPixmap(path)
            self.image_label.setPixmap(
                pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            self.image_label.setText(f"无法显示图片：\n{e}")

    def _predict(self):
        if not all([self.current_image_path, self.model]):
            QMessageBox.warning(self, "提示", "请先加载模型并选择一张图片。")
            return

        if not self.knowledge_base:
            QMessageBox.warning(self, "提示", "知识库未加载，无法进行识别。请重新加载模型。")
            return

        self.set_ui_lock(True)
        QApplication.processEvents()

        try:
            start_time = time.time()
            image_size = self.loaded_model_config.get("image_size", 224)
            transform = transforms.Compose([
                transforms.Resize((image_size, image_size), antialias=True),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

            img = Image.open(self.current_image_path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.sigmoid(logits)

            k = min(5, len(self.idx_to_label))
            topk_probs, topk_indices = torch.topk(probs.flatten(), k=k)

            results = []
            for i in range(k):
                prob = topk_probs[i].item()
                idx_str = str(topk_indices[i].item())
                kb_entry = self.knowledge_base.get(idx_str, {"readable_name": f"未知标签_{idx_str}"})
                readable_name = kb_entry.get("readable_name", f"解析错误_{idx_str}")

                results.append({"readable_name": readable_name, "confidence": prob})

            processing_time = time.time() - start_time
            self._on_prediction_finished(results, processing_time)

        except Exception:
            self._on_prediction_error(f"处理图像时出错：\n{traceback.format_exc()}")
        finally:
            self.set_ui_lock(False)

    def _clear_results(self):
        while self.result_layout.count():
            child = self.result_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.txt_detail.clear()

    def _on_prediction_finished(self, results, proc_time):
        self._clear_results()
        for i, res in enumerate(results, 1):
            on_click = partial(self._fetch_control_strategy, res["readable_name"])
            card = ResultCard(res["readable_name"], res["confidence"], i, on_click)
            self.result_layout.addWidget(card)
        self.result_layout.addStretch()

        details = [f"识别耗时: {proc_time:.3f} 秒"]
        details.append("\nTop-5 预测:")
        for i, res in enumerate(results, 1):
            details.append(f"{i}. {res['readable_name']}  ({res['confidence']:.2%})")

        details.append("\n\n点击结果卡片右侧的【获取防治策略】按钮，查看详细解决方案。")
        self.txt_detail.setText("\n".join(details))
    def _fetch_control_strategy(self, pest_name):
        """
        使用 DeepSeek 生成中文策略资料摘要。
        """
        if not STRATEGY_ENABLED:
            QMessageBox.critical(self, "功能不可用", f"防治策略查询当前不可用。\n\n{STRATEGY_STATUS}")
            return

        self.txt_detail.setText(f"正在为您整理“{pest_name}”的相关资料，请稍候...")
        QApplication.processEvents()

        try:
            strategy = fetch_strategy_with_deepseek(pest_name)
            summary = [f"--- 关于“{pest_name}”的资料摘要 ---", "", strategy["summary"]]

            if strategy["items"]:
                summary.append("")
                for i, item in enumerate(strategy["items"], 1):
                    summary.append(f"{i}. {item['title']}")
                    summary.append(item["content"] or "暂无摘要内容。")
                    if item["url"]:
                        summary.append(f"来源: {item['url']}")
                    summary.append("")

            if strategy["sources"]:
                summary.append("参考来源:")
                for source in strategy["sources"]:
                    source_line = source["title"]
                    if source["url"]:
                        source_line += f" - {source['url']}"
                    summary.append(source_line)

            self.txt_detail.setText("\n".join(summary).strip())

        except Exception:
            error_message = f"资料查询过程中发生错误：\n{traceback.format_exc()}"
            self.txt_detail.setText(error_message)
            QMessageBox.critical(self, "处理错误", error_message)

    def _on_prediction_error(self, msg):
        QMessageBox.critical(self, "识别错误", msg)

    def set_ui_lock(self, locked):
        self.btn_predict.setEnabled(not locked)
        self.btn_select_image.setEnabled(not locked)
        self.btn_load_model.setEnabled(not locked)
        self.model_combo.setEnabled(not locked)
        self.btn_predict.setText("正在识别..." if locked else "开始识别")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = CropDiseaseClassifierGUI()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


