# model.py (随机深度最终版 - 已修复模型加载问题)
"""
模型定义与加载 - 最终版
功能：
- 为模型添加 drop_path_rate 参数，以支持随机深度正则化。
- 实现了对多标签模型和标签文件的加载。
- 所有功能与最终版GUI和训练脚本完全兼容。
"""
import torch
import torch.nn as nn
import timm
import json
from pathlib import Path
import warnings


class CropDiseaseClassifier(nn.Module):
    """
    农作物病虫害分类器模型 - 支持多标签和随机深度
    """
    def __init__(self, model_name: str, pretrained: bool, num_classes: int, hidden_dim: int = 1024,
                 drop_rate: float = 0.5, drop_path_rate: float = 0.0, checkpoint_path: str = None):
        super().__init__()

        if checkpoint_path and Path(checkpoint_path).exists():
            print(f"   - 正在从本地路径加载预训练权重: {checkpoint_path}")
            self.backbone = timm.create_model(
                model_name, pretrained=True, num_classes=0,
                drop_path_rate=drop_path_rate, checkpoint_path=checkpoint_path
            )
        else:
            if checkpoint_path:
                warnings.warn(f"⚠️ 警告：提供的本地权重路径不存在 '{checkpoint_path}'。将尝试从网络下载。")
            self.backbone = timm.create_model(
                model_name, pretrained=pretrained, num_classes=0,
                drop_path_rate=drop_path_rate
            )

        self.num_features = self.backbone.num_features

        self.classifier = nn.Sequential(
            nn.Linear(self.num_features, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(drop_rate),
            nn.Linear(hidden_dim, num_classes)
        )
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        logits = self.classifier(features)
        return logits


def load_model_with_labels(model_checkpoint_path: str):
    """
    加载我们自己已训练的多标签模型及其对应的标签映射。
    """
    model_path = Path(model_checkpoint_path)
    model_dir = model_path.parent

    label_map_path = model_dir / "label_to_idx_multilabel.json"
    idx_map_path = model_dir / "idx_to_label_multilabel.json"

    if not idx_map_path.exists():
        print(f"警告: 未找到多标签标签文件，尝试加载旧版单标签文件...")
        label_map_path = model_dir / "label_to_idx.json"
        idx_map_path = model_dir / "idx_to_label.json"

    if not model_path.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    if not label_map_path.exists() or not idx_map_path.exists():
        raise FileNotFoundError(f"在模型目录 {model_dir} 中找不到对应的标签映射文件。")

    print(f"正在加载标签映射文件: {idx_map_path}")
    with open(idx_map_path, 'r', encoding='utf-8') as f:
        idx_to_label = json.load(f)

    idx_to_label = {str(k): v for k, v in idx_to_label.items()}

    num_classes = len(idx_to_label)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    try:
        # FIX: 将 weights_only 设置为 False。
        # 因为我们保存的检查点文件中包含了Numpy的数值类型 (如 val_acc, val_f1)，
        # 这些类型在 weights_only=True 的严格模式下不被允许。
        # 由于这是我们自己创建的文件，所以这样做是完全安全的。
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)

        saved_config = checkpoint.get("config", {})
        actual_model_name = saved_config.get("model_name", "tf_efficientnet_b4.ns_jft_in1k")
        hidden_dim = saved_config.get("hidden_dim", 1024)
        drop_rate = saved_config.get("drop_rate", 0.4)
        drop_path_rate = saved_config.get("drop_path_rate", 0.0)

        model = CropDiseaseClassifier(
            model_name=actual_model_name,
            pretrained=False,
            num_classes=num_classes,
            hidden_dim=hidden_dim,
            drop_rate=drop_rate,
            drop_path_rate=drop_path_rate
        ).to(device)

        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        print(f"✅ 成功加载您训练的模型：{model_path}")

        return model, None, idx_to_label, saved_config

    except Exception as e:
        print(f"❌ 加载模型权重失败: {e}")
        raise