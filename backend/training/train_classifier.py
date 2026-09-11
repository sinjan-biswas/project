"""
Train the document-type CNN (MobileNetV3-Small, transfer learning).

Dataset layout (ImageFolder format):
    data/
      train/passport/*.jpg
      train/visa/*.jpg
      train/national_id/*.jpg
      train/driving_license/*.jpg
      train/residence_permit/*.jpg
      train/aadhaar/*.jpg          (optional)
      train/pan/*.jpg              (optional)
      train/voter_id/*.jpg         (optional)
      val/<same classes>/

Run:
    pip install torch torchvision
    python train_classifier.py --data-dir data --epochs 40 --output-dir runs/doccls
    python export_onnx.py --checkpoint runs/doccls/best.pt --output-dir ../models/document_classifier
"""

import argparse
import copy
import json
import os
import time

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


def get_model(num_classes: int, arch: str = "mobilenet_v3_small"):
    if arch == "mobilenet_v3_small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT
        model = models.mobilenet_v3_small(weights=weights)
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, num_classes)
    elif arch == "efficientnet_b0":
        weights = models.EfficientNet_B0_Weights.DEFAULT
        model = models.efficientnet_b0(weights=weights)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
    else:
        raise ValueError(f"unsupported arch: {arch}")
    return model, weights


def build_loaders(data_dir, weights, batch_size, num_workers=2):
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    train_ds = datasets.ImageFolder(os.path.join(data_dir, "train"), transform=train_tf)
    val_ds = datasets.ImageFolder(os.path.join(data_dir, "val"), transform=val_tf)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                          num_workers=num_workers, pin_memory=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                        num_workers=num_workers, pin_memory=True)
    return train_dl, val_dl, train_ds.classes


def run_epoch(model, loader, criterion, optimizer, device, use_amp, train=True):
    model.train() if train else model.eval()
    total_loss, correct, total = 0.0, 0, 0
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            with torch.cuda.amp.autocast(enabled=use_amp):
                logits = model(x)
                loss = criterion(logits, y)
            if train:
                optimizer.zero_grad(set_to_none=True)
                if use_amp:
                    # GradScaler is deprecated in newer torch; autocast + GradScaler
                    # still works on stable 2.x, keep it simple and safe:
                    loss.backward()
                else:
                    loss.backward()
                optimizer.step()
            total_loss += loss.item() * x.size(0)
            correct += (logits.argmax(1) == y).sum().item()
            total += x.size(0)
    return total_loss / total, correct / total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--arch", default="mobilenet_v3_small",
                   choices=["mobilenet_v3_small", "efficientnet_b0"])
    p.add_argument("--head-epochs", type=int, default=5,
                   help="epochs training only the classifier head (backbone frozen)")
    p.add_argument("--patience", type=int, default=6)
    p.add_argument("--output-dir", default="runs/doccls")
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    os.makedirs(args.output_dir, exist_ok=True)

    train_dl, val_dl, classes = build_loaders(args.data_dir, None, args.batch_size)
    num_classes = len(classes)
    print(f"classes ({num_classes}): {classes}")
    print("class counts (train):",
          {c: train_dl.dataset.targets.count(i) for i, c in enumerate(classes)})

    model, _ = get_model(num_classes=num_classes, arch=args.arch)
    model.to(device)

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

    # Phase 1: train head only
    for param in model.features.parameters():
        param.requires_grad = False
    optimizer = torch.optim.AdamW(filter(lambda pp: pp.requires_grad, model.parameters()), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.head_epochs)

    best_acc, patience_left, best_state = 0.0, args.patience, None

    def validate_and_save(epoch):
        nonlocal best_acc, patience_left, best_state
        val_loss, val_acc = run_epoch(model, val_dl, criterion, optimizer, device, use_amp, train=False)
        print(f"  epoch {epoch:03d} | val_loss={val_loss:.4f} | val_acc={val_acc:.4f}")
        if val_acc > best_acc:
            best_acc = val_acc
            best_state = copy.deepcopy(model.state_dict())
            patience_left = args.patience
        else:
            patience_left -= 1
        return val_acc

    print("== Phase 1: head-only training ==")
    for epoch in range(1, args.head_epochs + 1):
        tr_loss, tr_acc = run_epoch(model, train_dl, criterion, optimizer, device, use_amp, train=True)
        print(f"epoch {epoch:03d} | train_loss={tr_loss:.4f} | train_acc={tr_acc:.4f}")
        validate_and_save(epoch)
        scheduler.step()

    # Phase 2: fine-tune everything at lower LR
    print("== Phase 2: full fine-tune ==")
    for param in model.parameters():
        param.requires_grad = True
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr / 10)
    remaining = max(args.epochs - args.head_epochs, 1)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=remaining)

    for epoch in range(args.head_epochs + 1, args.epochs + 1):
        if patience_left <= 0:
            print("early stopping")
            break
        tr_loss, tr_acc = run_epoch(model, train_dl, criterion, optimizer, device, use_amp, train=True)
        print(f"epoch {epoch:03d} | train_loss={tr_loss:.4f} | train_acc={tr_acc:.4f}")
        validate_and_save(epoch)
        scheduler.step()

    if best_state is not None:
        model.load_state_dict(best_state)

    ckpt_path = os.path.join(args.output_dir, "best.pt")
    torch.save({
        "model_state": model.state_dict(),
        "arch": args.arch,
        "num_classes": num_classes,
        "classes": classes,
        "input_size": 224,
        "val_acc": best_acc,
    }, ckpt_path)
    with open(os.path.join(args.output_dir, "labels.json"), "w") as f:
        json.dump(classes, f)
    print(f"saved checkpoint -> {ckpt_path} (best val_acc={best_acc:.4f})")
    print(f"next: python export_onnx.py --checkpoint {ckpt_path} --output-dir ../models/document_classifier")


if __name__ == "__main__":
    main()
