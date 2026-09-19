import argparse
import json
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
from sklearn.metrics import classification_report
from tqdm import tqdm
import time
import os

# Copy training logic from train_classifier.py
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
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model

def set_backbone_frozen(model: nn.Module, frozen: bool) -> None:
    for p in model.features.parameters():
        p.requires_grad = not frozen

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out",  default="models/doc_classifier.pt")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--warmup-epochs", type=int, default=3)
    ap.add_argument("--batch",  type=int, default=32)
    ap.add_argument("--lr-head", type=float, default=1e-3)
    ap.add_argument("--lr-full", type=float, default=3e-4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--verbose", action="store_true", help="Print per-batch progress")
    args = ap.parse_args()

    # CUDA detection with fallback
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
    print(f"📊 Training: {args.epochs} epochs, {args.warmup_epochs} warmup epochs")
    print(f"📈 Batch size: {args.batch}, LR head: {args.lr_head}, LR full: {args.lr_full}")
    print(f"📂 Data: {args.data}/train (train) / {args.data}/valid (val)")

    train_dir = Path(args.data) / "train"
    valid_dir = Path(args.data) / "valid"
    if not train_dir.is_dir() or not valid_dir.is_dir():
        raise SystemExit(f"Expected {train_dir}/ and {valid_dir}/. Create data/train/<class>/ and data/valid/<class> first.")

    train_ds = datasets.ImageFolder(train_dir, transform=TRAIN_TF)
    val_ds   = datasets.ImageFolder(valid_dir, transform=VAL_TF)
    if train_ds.classes != val_ds.classes:
        raise SystemExit(f"Class mismatch!\n  train: {train_ds.classes}\n  valid: {val_ds.classes}")
    class_names = train_ds.classes
    print(f"🎨 Classes ({len(class_names)}): {class_names}")
    print(f"📸 Train: {len(train_ds)} images, Val: {len(val_ds)} images")

    train_loader = DataLoader(train_ds, batch_size=args.batch,
                              shuffle=True, num_workers=args.workers,
                              pin_memory=True, drop_last=len(train_ds) > args.batch)
    val_loader = DataLoader(val_ds, batch_size=args.batch,
                            shuffle=False, num_workers=args.workers,
                            pin_memory=True)

    model = build_model(len(class_names)).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    best_acc = 0.0
    start_time = time.time()

    # Phase 1: frozen backbone
    set_backbone_frozen(model, True)
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr_head, weight_decay=1e-4,
    )
    scheduler = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs} [FROZEN]",
                    position=epoch, leave=False, ncols=80, colour='blue')
        running_loss = 0.0
        batch_count = 0

        for imgs, labels in pbar:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(imgs), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * imgs.size(0)
            batch_count += 1
            if args.verbose:
                pbar.set_postfix(loss=f"{loss.item():.3f}")
        pbar.close()

        # Unfreeze at warmup+1
        if epoch == args.warmup_epochs + 1:
            print(f"\n🔓 Unfreezing backbone at epoch {epoch}")
            set_backbone_frozen(model, False)
            optimizer = torch.optim.AdamW(
                model.parameters(), lr=args.lr_full, weight_decay=1e-4,
            )
            remaining = args.epochs - args.warmup_epochs
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=remaining, eta_min=1e-6,
            )
            print(f"📈 Using cosine LR from {args.lr_full} to 0 over {remaining} epochs")

        # Validation
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
        acc = sum(p == l for p in zip(all_preds, all_labels)) / len(all_labels)
        elapsed = time.time() - start_time
        print(f"📊 Epoch {epoch:2d}: val_acc={acc:.4f} | val_loss={val_loss/len(val_ds):.4f} | time={elapsed:.1f}s")

        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), Path(args.out))
            print(f"💾 Saved best model: {args.out} (acc={acc:.4f})")

        if scheduler is not None:
            scheduler.step()

    # Final report
    total_time = time.time() - start_time
    print(f"\n🎉 Training complete! Total time: {total_time:.1f}s")
    print(f"📈 Best validation accuracy: {best_acc:.4f}")
    print(f"✨ Per-class report:")
    print(classification_report(all_labels, all_preds,
                                target_names=class_names, zero_division=0))

if __name__ == "__main__":
    main()