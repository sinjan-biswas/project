import argparse
import json
from pathlib import Path

from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="PIL")

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
from sklearn.metrics import classification_report, precision_recall_fscore_support
from sklearn.utils.class_weight import compute_class_weight
from tqdm import tqdm


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

TRAIN_TF = transforms.Compose([
    transforms.Resize((232, 232)),
    transforms.CenterCrop(224),
    transforms.RandomRotation(5),
    transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.10),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

VAL_TF = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


def build_model(num_classes: int) -> nn.Module:
    weights = EfficientNet_B0_Weights.IMAGENET1K_V1
    model = efficientnet_b0(weights=weights)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    return model


def set_backbone_frozen(model: nn.Module, frozen: bool,
                        frozen_blocks: int = 6) -> None:
    """Control which feature blocks are trainable.

    - frozen=True  -> freeze ALL feature blocks (phase-1 head-only training)
    - frozen=False -> freeze only the first `frozen_blocks`, keep the rest
                      + the classifier head trainable (phase-2 fine-tune)
    """
    for i, block in enumerate(model.features):
        trainable = (not frozen) and (i >= frozen_blocks)
        for p in block.parameters():
            p.requires_grad = trainable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out",  default="models/doc_classifier.pt")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--warmup-epochs", type=int, default=3)
    ap.add_argument("--batch",  type=int, default=32)
    ap.add_argument("--lr-head", type=float, default=1e-3)
    ap.add_argument("--lr-full", type=float, default=3e-4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--frozen-blocks", type=int, default=6,
                    help="Number of early EfficientNet blocks to keep frozen "
                         "during phase-2 fine-tuning (0-9)")
    ap.add_argument("--class-weights", action="store_true",
                    help="Weight loss by inverse class frequency (recommended "
                         "for imbalanced datasets)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"  GPU : {torch.cuda.get_device_name(0)}")

    # ---- Data ----------------------------------------------------------
    train_dir = Path(args.data) / "train"
    valid_dir = Path(args.data) / "valid"
    if not train_dir.is_dir() or not valid_dir.is_dir():
        raise SystemExit(f"Expected {train_dir}/ and {valid_dir}/")

    train_ds = datasets.ImageFolder(train_dir, transform=TRAIN_TF)
    val_ds   = datasets.ImageFolder(valid_dir, transform=VAL_TF)

    if train_ds.classes != val_ds.classes:
        raise SystemExit(
            f"Class mismatch:\n  train: {train_ds.classes}\n  valid: {val_ds.classes}"
        )

    class_names = train_ds.classes
    print(f"Classes ({len(class_names)}): {class_names}")
    print(f"Train: {len(train_ds)}  Valid: {len(val_ds)}")
    for name in class_names:
        n_tr = sum(1 for p in (train_dir / name).rglob("*")
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
        n_va = sum(1 for p in (valid_dir / name).rglob("*")
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
        print(f"  {name:<18} train={n_tr:<5} valid={n_va}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.workers, pin_memory=True,
                              drop_last=len(train_ds) > args.batch)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                            num_workers=args.workers, pin_memory=True)

    # ---- Model ---------------------------------------------------------
    model = build_model(len(class_names)).to(device)

    # ---- Loss (optional class weighting) -------------------------------
    if args.class_weights:
        labels = [s[1] for s in train_ds.samples]
        w = compute_class_weight("balanced",
                                 classes=np.arange(len(class_names)),
                                 y=labels)
        w = torch.tensor(w, dtype=torch.float32).to(device)
        print("Class weights:",
              {n: round(float(x), 2) for n, x in zip(class_names, w)})
        criterion = nn.CrossEntropyLoss(weight=w, label_smoothing=0.05)
    else:
        criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    # ---- Phase 1: full backbone frozen ---------------------------------
    set_backbone_frozen(model, True)
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr_head, weight_decay=1e-4,
    )
    scheduler = None

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = out_path.with_suffix(".json")

    best_acc = 0.0

    for epoch in range(1, args.epochs + 1):
        # ---- Phase transition ------------------------------------------
        if epoch == args.warmup_epochs + 1:
            print(f"\n-> Unfreezing last {9 - args.frozen_blocks} blocks "
                  f"(keeping first {args.frozen_blocks} frozen)")
            set_backbone_frozen(model, False, frozen_blocks=args.frozen_blocks)
            optimizer = torch.optim.AdamW(
                filter(lambda p: p.requires_grad, model.parameters()),
                lr=args.lr_full, weight_decay=1e-4,
            )
            remaining = args.epochs - args.warmup_epochs
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=remaining, eta_min=1e-6,
            )

        # ---- Train ------------------------------------------------------
        model.train()
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}")
        running_loss = 0.0
        for imgs, labels in pbar:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(imgs), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * imgs.size(0)
            pbar.set_postfix(loss=f"{loss.item():.3f}",
                             lr=f"{optimizer.param_groups[0]['lr']:.2e}")

        if scheduler is not None:
            scheduler.step()

        # ---- Validate ---------------------------------------------------
        model.eval()
        all_preds, all_labels = [], []
        val_loss = 0.0
        with torch.inference_mode():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                logits = model(imgs)
                val_loss += criterion(logits, labels).item() * imgs.size(0)
                preds = logits.argmax(dim=1).cpu()
                all_preds.extend(preds.tolist())
                all_labels.extend(labels.cpu().tolist())

        acc = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)
        print(f"  val_acc={acc:.4f}  val_loss={val_loss/len(val_ds):.4f}  "
              f"train_loss={running_loss/len(train_ds):.4f}")

        if args.verbose:
            p, r, f1, _ = precision_recall_fscore_support(
                all_labels, all_preds, zero_division=0,
                labels=list(range(len(class_names))),
            )
            for i, name in enumerate(class_names):
                print(f"    {name:<18} P={p[i]:.3f} R={r[i]:.3f} F1={f1[i]:.3f}")

        # ---- Checkpoint -------------------------------------------------
        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), out_path)
            meta_path.write_text(json.dumps({
                "classes": class_names,
                "val_acc": acc,
                "epoch": epoch,
                "arch": "efficientnet_b0",
                "input_size": 224,
                "imagenet_mean": IMAGENET_MEAN,
                "imagenet_std":  IMAGENET_STD,
            }, indent=2))
            print(f"  saved -> {out_path}  (best={best_acc:.4f})")

    print(f"\nBest val_acc: {best_acc:.4f}")
    print("\nPer-class report on last epoch:")
    print(classification_report(all_labels, all_preds,
                                target_names=class_names, zero_division=0))


if __name__ == "__main__":
    main()