# gui_app.py (v3.7 - OpenAI 鍏煎绛栫暐鏌ヨ鐗?
"""
鍥惧舰鐢ㄦ埛鐣岄潰锛圙UI锛夊簲鐢ㄧ▼搴?- v3.7 OpenAI 鍏煎绛栫暐鏌ヨ鐗?
鍔熻兘锛?
- [鏍稿績淇] 闃叉不绛栫暐鏌ヨ鏀逛负璋冪敤 OpenAI 鍏煎鎺ュ彛锛屼笉鍐嶄緷璧?Tavily 鍜岀炕璇戜腑杞€?
- [浼樺寲] 鐩存帴杈撳嚭涓枃缁撴瀯鍖栬祫鏂欙紝鍑忓皯棰濆澶勭悊姝ラ銆?
- [闆嗘垚] 鏀寔閫氳繃 API Key / Base URL / Model 涓夐」閰嶇疆鎺ュ叆绗笁鏂瑰吋瀹规湇鍔°€?
- 闆嗘垚鐭ヨ瘑搴?knowledge_base.json)锛屽皢妯″瀷杈撳嚭鐨勫唴閮ㄦ爣绛惧疄鏃惰浆鎹负鐢ㄦ埛鍙鐨勭梾铏鍚嶇О銆?
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

# ======================= OpenAI 鍏煎绛栫暐鏌ヨ闆嗘垚 =======================
OPENAI_COMPAT_API_KEY = (os.getenv("OPENAI_COMPAT_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "").strip()
OPENAI_COMPAT_MODEL = (
    os.getenv("OPENAI_COMPAT_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")).strip() or "deepseek-chat"
)
OPENAI_COMPAT_BASE_URL = (
    os.getenv("OPENAI_COMPAT_BASE_URL", os.getenv("DEEPSEEK_API_URL", "https://oapi.uk/v1")).strip()
    or "https://oapi.uk/v1"
)


def get_strategy_status():
    if not OPENAI_COMPAT_API_KEY:
        return False, "鏈厤缃?OpenAI 鍏煎鎺ュ彛 API Key銆?
    if not OPENAI_COMPAT_BASE_URL:
        return False, "鏈厤缃?OpenAI 鍏煎鎺ュ彛 Base URL銆?
    return True, "OpenAI 鍏煎绛栫暐鏈嶅姟鍙敤銆?


def build_chat_completions_url():
    base_url = OPENAI_COMPAT_BASE_URL.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


STRATEGY_ENABLED, STRATEGY_STATUS = get_strategy_status()


def create_strategy_payload(pest_name):
    system_prompt = (
        "浣犳槸涓€鍚嶅啘涓氭淇濊祫鏂欐暣鐞嗗姪鎵嬨€?
        "璇峰洿缁曠敤鎴锋彁渚涚殑鐥呰櫕瀹冲悕绉帮紝杈撳嚭缁撴瀯鍖栫殑涓枃璧勬枡鎽樿銆?
        "涓嶈缂栭€犵簿纭嵂鍓傚墏閲忋€佹硶瑙勭粨璁烘垨鏈€鏂版斂绛栥€?
        "鑻ヤ俊鎭笉澶熺‘瀹氾紝瑕佹槑纭彁绀轰粎渚涘弬鑰冿紝闇€瑕佺粨鍚堝綋鍦板啘鎶€寤鸿銆?
        "璇蜂弗鏍艰緭鍑?JSON 瀵硅薄锛屽寘鍚?summary銆乮tems銆乻ources 涓変釜瀛楁銆?
        "items 鏄暟缁勶紝姣忛」鍖呭惈 title銆乧ontent銆乽rl銆?
        "濡傛灉娌℃湁鐪熷疄鏉ユ簮閾炬帴锛寀rl 缃负绌哄瓧绗︿覆銆?
        "sources 鏄暟缁勶紝姣忛」鍖呭惈 title銆乽rl銆?
    )
    user_prompt = (
        f"璇锋暣鐞嗏€渰pest_name}鈥濈殑鐩稿叧璧勬枡锛岄噸鐐瑰寘鎷細"
        "鍏稿瀷鐥囩姸鎴栧嵄瀹宠〃鐜般€佸父瑙佸彂鐢熸潯浠躲€佺敯闂村鐞嗘€濊矾銆佺患鍚堥槻娌诲缓璁€佷娇鐢ㄦ彁閱掋€?
        "杈撳嚭瑕侀€傚悎妗岄潰绔洿鎺ュ睍绀猴紝璇█绠€娲侊紝涓嶈浣跨敤 Markdown銆?
    )
    return {
        "model": OPENAI_COMPAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
        "stream": False,
    }


def fetch_strategy_with_service(pest_name):
    payload = create_strategy_payload(pest_name)
    request = urllib.request.Request(
        build_chat_completions_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_COMPAT_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"绛栫暐鏈嶅姟璇锋眰澶辫触: HTTP {exc.code} {error_body}") from exc
    except Exception as exc:
        raise RuntimeError(f"绛栫暐鏈嶅姟璇锋眰澶辫触: {exc}") from exc

    try:
        response_data = json.loads(raw)
        content = response_data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"鏃犳硶瑙ｆ瀽绛栫暐鏈嶅姟鍝嶅簲: {exc}") from exc

    try:
        structured = json.loads(content)
    except json.JSONDecodeError:
        structured = {
            "summary": f"宸叉暣鐞?{pest_name} 鐨勭浉鍏宠祫鏂欍€?,
            "items": [{"title": f"{pest_name} 璧勬枡鎽樿", "content": content, "url": ""}],
            "sources": [],
        }

    items = []
    for item in structured.get("items", []):
        items.append(
            {
                "title": str(item.get("title", "鐩稿叧璧勬枡")),
                "content": str(item.get("content", "")),
                "url": str(item.get("url", "")),
            }
        )

    sources = []
    for source in structured.get("sources", []):
        sources.append(
            {
                "title": str(source.get("title", "鍙傝€冭祫鏂?)),
                "url": str(source.get("url", "")),
            }
        )

    return {
        "summary": str(structured.get("summary", f"宸叉暣鐞?{pest_name} 鐨勭浉鍏宠祫鏂欍€?)),
        "items": items,
        "sources": sources,
    }
# ===================================================================

from model import load_model_with_labels


# =========================== 鑷畾涔夋帶浠?========================= #
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

        lbl_conf = QLabel(f"缃俊搴? {confidence:.2%}")
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

        btn_strategy = QPushButton("鑾峰彇闃叉不绛栫暐")
        btn_strategy.setFont(QFont("Microsoft YaHei", 9))
        btn_strategy.setCursor(Qt.PointingHandCursor)
        btn_strategy.setStyleSheet(
            "QPushButton {background:#e7f3ff; color:#0056b3; border:1px solid #b8d6fb; border-radius:12px; padding: 5px 10px;} QPushButton:hover {background:#d0e7ff;}")
        btn_strategy.clicked.connect(on_strategy_click)
        if not STRATEGY_ENABLED:
            btn_strategy.setEnabled(False)
            btn_strategy.setText("绛栫暐鏌ヨ涓嶅彲鐢?)

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


# ============================= 涓荤晫闈?============================ #
class CropDiseaseClassifierGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.idx_to_label = None, {}
        self.knowledge_base = {}
        self.loaded_model_name, self.current_image_path = "鏈煡", ""
        self.loaded_model_config = {}
        self._init_ui()
        self._scan_models()

    def _init_ui(self):
        self.setWindowTitle("穹农智核（AgriOmniCore）v3.7（OpenAI兼容策略查询版）")
        self.setMinimumSize(1200, 800)
        central = QWidget(self);
        self.setCentralWidget(central)
        main = QHBoxLayout(central);
        splitter = QSplitter(Qt.Horizontal);
        main.addWidget(splitter)
        left = QWidget();
        left_layout = QVBoxLayout(left);
        splitter.addWidget(left)

        grp_model = QGroupBox("1. 妯″瀷閫夋嫨");
        v_model = QVBoxLayout(grp_model)
        self.model_combo = QComboBox();
        self.model_combo.addItem("璇蜂粠鍒楄〃涓€夋嫨鎴栨祻瑙堟湰鍦版ā鍨嬧€?)
        self.btn_browse_model = ModernButton("娴忚妯″瀷鏂囦欢");
        self.btn_load_model = ModernButton("鍔犺浇閫変腑妯″瀷", primary=True);
        self.lbl_model_state = QLabel("妯″瀷鐘舵€? 鏈姞杞?);
        self.lbl_model_state.setStyleSheet("color:red;font-weight:bold;padding:5px;")
        v_model.addWidget(self.model_combo);
        v_model.addWidget(self.btn_browse_model);
        v_model.addWidget(self.btn_load_model)

        grp_img = QGroupBox("2. 鍥惧儚璇嗗埆");
        v_img = QVBoxLayout(grp_img)
        self.image_label = QLabel("璇峰厛鍔犺浇妯″瀷锛岀劧鍚庨€夋嫨鍥惧儚");
        self.image_label.setMinimumSize(400, 400);
        self.image_label.setAlignment(Qt.AlignCenter);
        self.image_label.setWordWrap(True)
        self.image_label.setStyleSheet(
            "QLabel{border:3px dashed #dee2e6;border-radius:15px;background:#f8f9fa;color:#6c757d;font-size:14px;}")
        h_btns = QHBoxLayout()
        self.btn_select_image = ModernButton("閫夋嫨鍥惧儚", primary=True)
        self.btn_predict = ModernButton("寮€濮嬭瘑鍒?)
        h_btns.addWidget(self.btn_select_image);
        h_btns.addWidget(self.btn_predict)
        v_img.addWidget(self.image_label);
        v_img.addLayout(h_btns)

        grp_info = QGroupBox("妯″瀷淇℃伅");
        v_info = QVBoxLayout(grp_info)
        self.txt_model_info = QTextEdit("璇峰厛閫夋嫨骞跺姞杞芥ā鍨嬧€?);
        self.txt_model_info.setReadOnly(True)
        v_info.addWidget(self.txt_model_info)
        left_layout.addWidget(grp_model);
        left_layout.addWidget(self.lbl_model_state);
        left_layout.addWidget(grp_img);
        left_layout.addWidget(grp_info)

        right = QWidget();
        right_layout = QVBoxLayout(right);
        splitter.addWidget(right)
        grp_res = QGroupBox("璇嗗埆缁撴灉");
        v_res = QVBoxLayout(grp_res)
        scroll = QScrollArea();
        scroll.setWidgetResizable(True);
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.result_container = QWidget();
        self.result_layout = QVBoxLayout(self.result_container);
        self.result_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.result_container);
        v_res.addWidget(scroll)

        grp_detail = QGroupBox("璇︾粏淇℃伅涓庨槻娌荤瓥鐣?);
        v_detail = QVBoxLayout(grp_detail)
        self.txt_detail = QTextEdit();
        self.txt_detail.setReadOnly(True);
        self.txt_detail.setFont(QFont("Microsoft YaHei", 10))
        self.txt_detail.setMinimumHeight(220)
        v_detail.addWidget(self.txt_detail)
        right_layout.addWidget(grp_res);
        right_layout.addWidget(grp_detail)

        self.statusBar().showMessage("灏辩华 - 璇峰厛鍔犺浇妯″瀷")
        splitter.setSizes([600, 800])

        self.btn_browse_model.clicked.connect(self._browse_model)
        self.btn_load_model.clicked.connect(self._load_selected_model)
        self.btn_select_image.clicked.connect(self._select_image)
        self.btn_predict.clicked.connect(self._predict)

        self.btn_load_model.setEnabled(False)
        self.btn_select_image.setEnabled(False)
        self.btn_predict.setEnabled(False)

        if not STRATEGY_ENABLED:
            self.statusBar().showMessage(f"璀﹀憡锛氶槻娌荤瓥鐣ユ煡璇㈠綋鍓嶄笉鍙敤銆倇STRATEGY_STATUS}")

    def _scan_models(self):
        model_dir = Path(__file__).resolve().parent.parent / "trained_models"
        self.model_combo.clear()
        self.model_combo.addItem("璇蜂粠鍒楄〃涓€夋嫨鎴栨祻瑙堟湰鍦版ā鍨嬧€?)
        if model_dir.is_dir():
            pths = sorted([p for p in model_dir.glob("*.pth")], key=os.path.getmtime, reverse=True)
            for p in pths:
                self.model_combo.addItem(p.name, str(p))
        if self.model_combo.count() > 1:
            self.btn_load_model.setEnabled(True)

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "閫夋嫨妯″瀷鏂囦欢",
                                              str(Path(__file__).resolve().parent.parent / "trained_models"),
                                              "PyTorch妯″瀷 (*.pth)")
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
                QMessageBox.critical(self, "閿欒",
                                     f"鐭ヨ瘑搴撴枃浠?'knowledge_base.json' 鏈壘鍒帮紒\n璇风‘淇濆畠涓庢ā鍨嬫枃浠跺湪鍚屼竴鐩綍涓嬨€?)
                return

            with open(knowledge_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)

            model_name = self.loaded_model_config.get('model_name', '鏈煡')
            self.lbl_model_state.setText(f"妯″瀷宸插姞杞? {model_name}")
            self.lbl_model_state.setStyleSheet("color:green;font-weight:bold;")
            self.btn_select_image.setEnabled(True)
            self.txt_model_info.setText(f"妯″瀷鍚嶇О: {model_name}\n"
                                        f"鐭ヨ瘑搴撶被鍒? {len(self.knowledge_base)}\n"
                                        f"鍥剧墖灏哄: {self.loaded_model_config.get('image_size', '鏈煡')}")
            self._clear_results()
            self.txt_detail.setText("妯″瀷鍜岀煡璇嗗簱鍔犺浇鎴愬姛锛岃閫夋嫨鍥剧墖杩涜璇嗗埆銆?)

        except Exception:
            QMessageBox.critical(self, "閿欒", f"妯″瀷鍔犺浇澶辫触:\n{traceback.format_exc()}")
            self.lbl_model_state.setText("鍔犺浇澶辫触");
            self.lbl_model_state.setStyleSheet("color:red;font-weight:bold;")

    def _select_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "閫夋嫨鍥惧儚鏂囦欢", "", "鍥剧墖鏂囦欢 (*.jpg *.jpeg *.png)")
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
            self.image_label.setText(f"鏃犳硶鏄剧ず鍥剧墖锛歕n{e}")

    def _predict(self):
        if not all([self.current_image_path, self.model]):
            QMessageBox.warning(self, "鎻愮ず", "璇峰厛鍔犺浇妯″瀷骞堕€夋嫨涓€寮犲浘鐗囥€?)
            return

        if not self.knowledge_base:
            QMessageBox.warning(self, "鎻愮ず", "鐭ヨ瘑搴撴湭鍔犺浇锛屾棤娉曡繘琛岃瘑鍒€傝閲嶆柊鍔犺浇妯″瀷銆?)
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
                kb_entry = self.knowledge_base.get(idx_str, {"readable_name": f"鏈煡鏍囩_{idx_str}"})
                readable_name = kb_entry.get("readable_name", f"瑙ｆ瀽閿欒_{idx_str}")

                results.append({"readable_name": readable_name, "confidence": prob})

            processing_time = time.time() - start_time
            self._on_prediction_finished(results, processing_time)

        except Exception:
            self._on_prediction_error(f"澶勭悊鍥惧儚鏃跺嚭閿欙細\n{traceback.format_exc()}")
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

        details = [f"璇嗗埆鑰楁椂: {proc_time:.3f} 绉?]
        details.append("\nTop-5 棰勬祴:")
        for i, res in enumerate(results, 1):
            details.append(f"{i}. {res['readable_name']}  ({res['confidence']:.2%})")

        details.append("\n\n鐐瑰嚮缁撴灉鍗＄墖鍙充晶鐨勩€愯幏鍙栭槻娌荤瓥鐣ャ€戞寜閽紝鏌ョ湅璇︾粏瑙ｅ喅鏂规銆?)
        self.txt_detail.setText("\n".join(details))

    def _fetch_control_strategy(self, pest_name):
        """
        浣跨敤 OpenAI 鍏煎鎺ュ彛鐢熸垚涓枃绛栫暐璧勬枡鎽樿銆?
        """
        if not STRATEGY_ENABLED:
            QMessageBox.critical(self, "鍔熻兘涓嶅彲鐢?, f"闃叉不绛栫暐鏌ヨ褰撳墠涓嶅彲鐢ㄣ€俓n\n{STRATEGY_STATUS}")
            return

        self.txt_detail.setText(f"姝ｅ湪涓烘偍鏁寸悊鈥渰pest_name}鈥濈殑鐩稿叧璧勬枡锛岃绋嶅€?..")
        QApplication.processEvents()

        try:
            strategy = fetch_strategy_with_service(pest_name)
            summary = [f"--- 鍏充簬鈥渰pest_name}鈥濈殑璧勬枡鎽樿 ---", "", strategy["summary"]]

            if strategy["items"]:
                summary.append("")
                for i, item in enumerate(strategy["items"], 1):
                    summary.append(f"{i}. {item['title']}")
                    summary.append(item["content"] or "鏆傛棤鎽樿鍐呭銆?)
                    if item["url"]:
                        summary.append(f"鏉ユ簮: {item['url']}")
                    summary.append("")

            if strategy["sources"]:
                summary.append("鍙傝€冩潵婧?")
                for source in strategy["sources"]:
                    source_line = source["title"]
                    if source["url"]:
                        source_line += f" - {source['url']}"
                    summary.append(source_line)

            self.txt_detail.setText("\n".join(summary).strip())

        except Exception:
            error_message = f"璧勬枡鏌ヨ杩囩▼涓彂鐢熼敊璇細\n{traceback.format_exc()}"
            self.txt_detail.setText(error_message)
            QMessageBox.critical(self, "澶勭悊閿欒", error_message)

    def _on_prediction_error(self, msg):
        QMessageBox.critical(self, "璇嗗埆閿欒", msg)

    def set_ui_lock(self, locked):
        self.btn_predict.setEnabled(not locked)
        self.btn_select_image.setEnabled(not locked)
        self.btn_load_model.setEnabled(not locked)
        self.model_combo.setEnabled(not locked)
        self.btn_predict.setText("姝ｅ湪璇嗗埆..." if locked else "寮€濮嬭瘑鍒?)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = CropDiseaseClassifierGUI()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()






