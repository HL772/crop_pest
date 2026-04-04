# train.py (B5模型 + 速度均衡最终版) - Validation Stability Fix
"""
最终训练脚本 - B5模型 + 456分辨率 + 速度均衡版
功能：
- 将num_workers设置为4，在保证稳定性的前提下达到更快的训练速度。
- 实现了完美的断点续练功能，可恢复轮数、优化器、学习率计划和历史图表数据。
- 所有其他功能完整，是最终交付版本。

[本次修改说明]:
- 在验证阶段（_eval_epoch）禁用了自动混合精度（AMP），强制使用float32计算，
  以彻底解决偶发性的 NaN loss 问题，确保训练稳定性。
"""
import os

os.environ['NO_ALBUMENTATIONS_UPDATE'] = '1'

import json, shutil, warnings, contextlib, gc
from pathlib import Path
from typing import Dict
import time
import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image

plt.rcParams['axes.unicode_minus'] = False

import numpy as np
import pandas as pd
from torchvision import transforms

import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from sklearn.metrics import f1_score, multilabel_confusion_matrix

from model import CropDiseaseClassifier

# ========== B5 + 速度均衡配置 ==========
CFG: Dict = {
    "resume_from_checkpoint": r"F:\machinelearning\shizhan\crop_pest_disease_classifier\trained_models\best_model_f1.pth",

    "model_name": "tf_efficientnet_b5.ns_jft_in1k",
    "image_size": 456,
    "pretrained": True,
    "local_pretrained_path": None,

    "batch_size": 4,
    "accum_steps": 4,

    "data_dir": r"F:\machinelearning\shizhan\crop_pest_disease_classifier\datasets\processed",
    "save_dir": r"F:\machinelearning\shizhan\crop_pest_disease_classifier\trained_models",

    "num_workers": 4,
    "amp": True,

    "epochs": 100,
    "lr": 1e-4,
    "min_lr": 1e-6,

    "wd": 1e-2,
    "drop_path_rate": 0.2,
    "smoothing": 0.1,

    "grad_clip": 1.0,

    "warmup_epochs": 10,

    "hidden_dim": 1024,
    "drop_rate": 0.5,
    "early_stop": 15,
    "plot_metrics": True,
}


# ========== AMP设置 ==========
def _setup_amp(cfg):
    use_cuda = torch.cuda.is_available()
    if not (cfg["amp"] and use_cuda):
        return contextlib.nullcontext(), None
    try:
        from torch.amp import autocast, GradScaler
        return autocast(device_type="cuda", dtype=torch.float16), GradScaler()
    except Exception as e:
        print(f"[⚠] AMP 初始化失败，已降级为 FP32 ({e})")
        cfg["amp"] = False
        return contextlib.nullcontext(), None


# ========== Dataset with Label Smoothing ==========
class MultiLabelCropDataset(Dataset):
    def __init__(self, csv_path: Path, tfm, smoothing: float = 0.0):
        self.data = pd.read_csv(csv_path)
        self.tfm = tfm
        self.smoothing = smoothing
        print(f"成功加载多标签数据集: {csv_path.name}, 包含 {len(self.data)} 个样本。")
        if self.smoothing > 0:
            print(f"✨ 已为此数据集启用标签平滑，平滑系数: {self.smoothing}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        img_path = row["image_path"]
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            warnings.warn(f"读取图像时发生错误，将使用黑色图片代替: {img_path}, Error: {e}")
            img = Image.new('RGB', (CFG['image_size'], CFG['image_size']), (0, 0, 0))

        img = self.tfm(img)

        hard_labels = torch.tensor(json.loads(row["labels"]), dtype=torch.float32)

        if self.smoothing > 0:
            soft_labels = hard_labels * (1.0 - self.smoothing) + 0.5 * self.smoothing
            return img, soft_labels, hard_labels
        else:
            return img, hard_labels, hard_labels


# ========== Trainer ==========
class Trainer:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.start_epoch = 1
        self.run_start_time = time.time()

        warnings.filterwarnings("ignore", category=UserWarning)
        if torch.cuda.is_available(): torch.backends.cudnn.benchmark = True

        IMG_SIZE = cfg['image_size']

        self.train_tf = transforms.Compose([
            transforms.TrivialAugmentWide(),
            transforms.ToTensor(),
            transforms.Resize((IMG_SIZE, IMG_SIZE), antialias=True),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        self.val_tf = transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        dd = Path(cfg["data_dir"])
        train_path = dd / "train_data_multilabel.csv";
        val_path = dd / "val_data_multilabel.csv"

        train_dataset = MultiLabelCropDataset(train_path, self.train_tf, smoothing=cfg.get("smoothing", 0.0))
        val_dataset = MultiLabelCropDataset(val_path, self.val_tf)

        dl_kwargs = {"num_workers": cfg["num_workers"], "pin_memory": True,
                     "persistent_workers": True if cfg["num_workers"] > 0 else False}
        self.train_loader = DataLoader(train_dataset, batch_size=cfg["batch_size"], shuffle=True, drop_last=True,
                                       **dl_kwargs)
        self.val_loader = DataLoader(val_dataset, batch_size=cfg["batch_size"] * 2, shuffle=False, **dl_kwargs)

        with open(dd / "idx_to_label_multilabel.json") as f:
            self.idx_to_label = {int(k): v for k, v in json.load(f).items()}
        num_classes = len(self.idx_to_label)

        is_resuming = cfg.get("resume_from_checkpoint") and Path(cfg["resume_from_checkpoint"]).exists()
        use_imagenet_pretrained = cfg["pretrained"] and not is_resuming

        self.model = CropDiseaseClassifier(
            model_name=cfg["model_name"], pretrained=use_imagenet_pretrained, num_classes=num_classes,
            hidden_dim=cfg["hidden_dim"], drop_rate=cfg["drop_rate"], drop_path_rate=cfg.get("drop_path_rate", 0.0),
            checkpoint_path=cfg.get("local_pretrained_path")
        ).to(self.device)
        print(f"✓ 多标签模型已实例化 (ImageNet Pretrained={use_imagenet_pretrained})")
        if 'b5' in cfg["model_name"]:
            print("✨ 您正在使用更强大的 EfficientNet-B5 模型，并以456px分辨率进行训练。")
            print("✨ 已启用强效抗过拟合策略！")

        self.optimizer = optim.AdamW(self.model.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
        self.lr_sched = optim.lr_scheduler.CosineAnnealingLR(self.optimizer, T_max=cfg['epochs'] - cfg['warmup_epochs'],
                                                             eta_min=cfg["min_lr"])

        self.criterion = nn.BCEWithLogitsLoss()
        self.autocast_ctx, self.scaler = _setup_amp(cfg)
        self.save_dir = Path(cfg["save_dir"]);
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.best_acc = 0.0;
        self.best_f1 = 0.0;
        self.no_improve = 0
        self.history = {'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': [], 'train_f1': [], 'val_f1': [],
                        'lr': []}

        if is_resuming:
            self._load_from_checkpoint(Path(cfg["resume_from_checkpoint"]))

    def _load_from_checkpoint(self, ckpt_path: Path):
        print(f"✈️ 正在从检查点恢复训练: {ckpt_path}")
        checkpoint = torch.load(ckpt_path, map_location=self.device, weights_only=False)

        self.model.load_state_dict(checkpoint['model_state_dict'])

        if 'optimizer_state_dict' in checkpoint:
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        if 'scheduler_state_dict' in checkpoint:
            self.lr_sched.load_state_dict(checkpoint['scheduler_state_dict'])
        if 'history' in checkpoint:
            self.history = checkpoint['history']

        self.best_acc = checkpoint.get("val_acc", 0.0)
        self.best_f1 = checkpoint.get("val_f1", 0.0)
        self.start_epoch = checkpoint.get("epoch", 0) + 1

        print(f"✅ 状态恢复成功！将从第 {self.start_epoch} 轮开始，历史最佳 F1: {self.best_f1:.4f}")

    def run(self):
        run_mode = "恢复训练" if self.start_epoch > 1 else "全新训练"
        print(f"🚀 开始{run_mode} ({self.cfg['model_name']}, {self.cfg['image_size']}px) - 设备: {self.device}")

        for epoch in range(self.start_epoch, self.cfg["epochs"] + 1):
            print(f"\nEpoch {epoch}/{self.cfg['epochs']} | LR: {self.optimizer.param_groups[0]['lr']:.3e}")
            if torch.cuda.is_available(): gc.collect(); torch.cuda.empty_cache()

            tr_loss, tr_acc, tr_f1 = self._train_epoch(epoch)
            vl_loss, val_acc, vl_f1, preds_binary, targets = self._eval_epoch()

            if np.isnan(vl_loss) or np.isnan(tr_loss):
                print(f"❌ NaN loss detected. Halting training.")
                break

            self.history['train_loss'].append(tr_loss);
            self.history['train_acc'].append(tr_acc);
            self.history['train_f1'].append(tr_f1)
            self.history['val_loss'].append(vl_loss);
            self.history['val_acc'].append(val_acc);
            self.history['val_f1'].append(vl_f1)
            self.history['lr'].append(self.optimizer.param_groups[0]['lr'])

            print(f" ▸ 训练损失: {tr_loss:.4f} | Acc: {tr_acc:.2f}% | F1: {tr_f1:.4f}")
            print(f" ▸ 验证损失: {vl_loss:.4f} | Acc (Exact Match): {val_acc:.2f}% | F1 (Samples): {vl_f1:.4f}")

            best_f1_updated = False
            if vl_f1 > self.best_f1:
                self.best_f1 = vl_f1;
                self.no_improve = 0
                self._save_ckpt("best_model_f1.pth", epoch)
                print(f"   ✓ F1分数创纪录，已更新 best_model_f1.pth (F1={self.best_f1:.4f})")
                best_f1_updated = True
            else:
                self.no_improve += 1

            if val_acc > self.best_acc:
                self.best_acc = val_acc
                self._save_ckpt("best_model_acc.pth", epoch)
                print(f"   ✓ 准确率创纪录，已更新 best_model_acc.pth (Acc={val_acc:.2f}%)")

            if epoch >= self.cfg["warmup_epochs"]:
                self.lr_sched.step()

            if self.cfg["plot_metrics"]:
                self._plot_metrics(epoch, is_final=False)
                if best_f1_updated:
                    pass

            if self.no_improve >= self.cfg["early_stop"]:
                print(f"提前停止于第 {epoch} 轮 — 验证集F1分数已连续 {self.no_improve} 轮未提升。")
                break

        total_time_str = f"总时间: {(time.time() - self.run_start_time) / 3600:.2f}小时"
        if self.start_epoch > 1:
            total_time_str = f"本次恢复训练耗时: {(time.time() - self.run_start_time) / 3600:.2f}小时"

        print(f"\n训练完成！{total_time_str}, 最终最佳F1: {self.best_f1:.4f}, 最终最佳Acc: {self.best_acc:.2f}%")
        if self.cfg["plot_metrics"]: self._plot_metrics(self.cfg["epochs"], is_final=True)

    def _train_epoch(self, epoch):
        self.model.train()
        total_loss, all_preds_binary, all_hard_targets = 0, [], []
        pbar = tqdm(self.train_loader, desc="训练")

        if self.start_epoch <= 1 and epoch <= self.cfg["warmup_epochs"]:
            warmup_factor = (epoch - 1) / self.cfg["warmup_epochs"]
            if warmup_factor == 0: warmup_factor = 1e-9
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = self.cfg["lr"] * warmup_factor

        self.optimizer.zero_grad()
        for i, (imgs, soft_labels_dev, hard_labels_dev) in enumerate(pbar):
            imgs, soft_labels_dev = imgs.to(self.device), soft_labels_dev.to(self.device)
            all_hard_targets.append(hard_labels_dev.cpu())

            with self.autocast_ctx:
                logits = self.model(imgs)
                loss = self.criterion(logits, soft_labels_dev)
                loss = loss / self.cfg['accum_steps']

            if self.scaler:
                self.scaler.scale(loss).backward()
            else:
                loss.backward()

            total_loss += loss.item()
            all_preds_binary.append((torch.sigmoid(logits) > 0.5).int().cpu())

            if (i + 1) % self.cfg['accum_steps'] == 0:
                if self.scaler:
                    self.scaler.unscale_(self.optimizer)
                if self.cfg.get("grad_clip"):
                    nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg["grad_clip"])

                if self.scaler:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()

                self.optimizer.zero_grad()

            current_preds = torch.cat(all_preds_binary).numpy()
            current_targets = torch.cat(all_hard_targets).numpy()
            running_f1 = f1_score(current_targets, current_preds, average='samples', zero_division=0)
            running_acc = 100 * np.all(current_preds == current_targets, axis=1).mean()
            pbar.set_postfix(loss=f"{total_loss / (i + 1) * self.cfg['accum_steps']:.4f}", acc=f"{running_acc:.2f}%",
                             f1=f"{running_f1:.4f}")

        final_preds = torch.cat(all_preds_binary).numpy()
        final_targets = torch.cat(all_hard_targets).numpy()
        train_f1 = f1_score(final_targets, final_preds, average='samples', zero_division=0)
        train_acc = 100 * np.all(final_preds == final_targets, axis=1).mean()

        avg_train_loss = total_loss * self.cfg['accum_steps'] / len(self.train_loader)

        return avg_train_loss, train_acc, train_f1

    def _eval_epoch(self):
        self.model.eval()
        total_loss, all_preds_binary, all_hard_targets = 0, [], []
        with torch.no_grad():
            for imgs, _, hard_labels_dev in tqdm(self.val_loader, desc="验证"):
                imgs, hard_labels_dev = imgs.to(self.device), hard_labels_dev.to(self.device)

                # FIX: Removed the autocast context for maximum stability during validation.
                # All calculations here will now be done in float32.
                logits = self.model(imgs)
                loss = self.criterion(logits, hard_labels_dev)

                total_loss += loss.item()

                all_preds_binary.append((torch.sigmoid(logits) > 0.5).int())
                all_hard_targets.append(hard_labels_dev.int())

        all_preds = torch.cat(all_preds_binary).cpu().numpy()
        all_targets = torch.cat(all_hard_targets).cpu().numpy()
        val_f1 = f1_score(all_targets, all_preds, average='samples', zero_division=0)
        val_acc = 100 * np.all(all_preds == all_targets, axis=1).mean()

        final_loss = total_loss / len(self.val_loader)

        return final_loss, val_acc, val_f1, all_preds, all_targets

    def _save_ckpt(self, fname, epoch):
        config_to_save = {k: v for k, v in self.cfg.items() if isinstance(v, (str, int, float, bool, type(None)))}
        config_to_save["num_classes"] = len(self.idx_to_label)

        ckpt = {
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scheduler_state_dict": self.lr_sched.state_dict(),
            "val_acc": self.history['val_acc'][-1],
            "val_f1": self.history['val_f1'][-1],
            "history": self.history,
            "config": config_to_save
        }
        if fname == "best_model_f1.pth":
            ckpt['val_f1'] = self.best_f1
        if fname == "best_model_acc.pth":
            ckpt['val_acc'] = self.best_acc

        torch.save(ckpt, self.save_dir / fname)

        for map_file in ["label_to_idx_multilabel.json", "idx_to_label_multilabel.json"]:
            if (Path(self.cfg["data_dir"]) / map_file).exists():
                shutil.copy(Path(self.cfg["data_dir"]) / map_file, self.save_dir / map_file)

    def _plot_metrics(self, current_epoch, is_final=False):
        if len(self.history['val_loss']) < 1: return

        fig, axes = plt.subplots(2, 3, figsize=(24, 12));
        fig.suptitle(f'Training Monitoring - Epoch: {current_epoch}', fontsize=20)

        x_axis = range(1, len(self.history['val_loss']) + 1)

        for i, (key, title) in enumerate([('loss', 'Loss'), ('acc', 'Accuracy'), ('f1', 'F1-Score')]):
            ax = axes[0, i]
            ax.plot(x_axis, self.history[f'train_{key}'], label=f'Training {title}', alpha=0.8)
            ax.plot(x_axis, self.history[f'val_{key}'], label=f'Validation {title}', lw=2)
            ax.set_title(f'{title} Curve');
            ax.legend();
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.set_xlabel("Epoch")

        train_acc_arr = np.array(self.history['train_acc']);
        val_acc_arr = np.array(self.history['val_acc'])
        if len(train_acc_arr) == len(val_acc_arr):
            axes[1, 0].plot(x_axis, train_acc_arr - val_acc_arr, label='Train-Val Acc Diff', color='orange')
        axes[1, 0].axhline(0, color='r', lw=1, linestyle='--');
        axes[1, 0].set_title('Overfitting Monitor');
        axes[1, 0].legend();
        axes[1, 0].grid(True, alpha=0.6);
        axes[1, 0].set_ylabel('Accuracy Difference (%)');
        axes[1, 0].set_xlabel("Epoch")

        axes[1, 1].plot(x_axis, self.history['lr'], label='Learning Rate');
        axes[1, 1].set_title('Learning Rate Schedule');
        axes[1, 1].legend();
        axes[1, 1].grid(True, alpha=0.6);
        axes[1, 1].set_xlabel("Epoch")

        axes[1, 2].plot(x_axis, self.history['val_acc'], 'o-', label='Validation Accuracy', alpha=0.7)
        axes[1, 2].plot(x_axis, [f * 100 for f in self.history['val_f1']], 's-', label='Validation F1 x 100', alpha=0.7)
        axes[1, 2].set_title('Performance Summary');
        axes[1, 2].legend();
        axes[1, 2].grid(True, alpha=0.6);
        axes[1, 2].set_ylabel('Score');
        axes[1, 2].set_xlabel("Epoch")

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plot_filename = self.save_dir / ("final_training_curves.png" if is_final else "current_training_curves.png")
        plt.savefig(plot_filename, dpi=150);
        plt.close(fig)


def main():
    if __name__ == "__main__":
        torch.manual_seed(42)
        np.random.seed(42)
        try:
            trainer = Trainer(CFG)
            trainer.run()
        except Exception as e:
            print(f"训练过程中发生未捕获的严重错误: {e}")
            import traceback
            traceback.print_exc()



main()