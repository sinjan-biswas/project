import random
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import models, transforms


IMG_SIZE = 384                       # ↑ from 256 — preserves splice artifacts
BATCH_SIZE = 16                      # ↓ from 32 (bigger images)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "models" / "tampernet" / "data" / "CASIA2"
CKPT_DIR = BASE_DIR / "models" / "tampernet"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

train_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomApply([transforms.ColorJitter(0.05, 0.05, 0.05)], p=0.3),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])
val_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


class CasiaDataset(Dataset):
    VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

    def __init__(self, root: Path, transform):
        def files(folder):
            return [p for p in folder.glob("*")
                    if p.is_file() and p.suffix.lower() in self.VALID_EXTS]
        self.samples = ([(p, 0) for p in files(root / "Authentic")]
                        + [(p, 1) for p in files(root / "Tampered")])
        if not self.samples:
            raise FileNotFoundError(f"No images under {root}")
        self.tf = transform

    def __len__(self): return len(self.samples)

    def __getitem__(self, i):
        p, y = self.samples[i]
        try:
            img = Image.open(p).convert("RGB")
        except Exception as e:
            print(f"[skip] {p}: {e}")
            return self.__getitem__((i + 1) % len(self.samples))
        return self.tf(img), y


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    print(f"Using device: {device}")

    base_ds = CasiaDataset(DATA_DIR, train_tf)
    base_val = CasiaDataset(DATA_DIR, val_tf)

    n = len(base_ds)
    val_size = int(0.15 * n)
    train_idx, val_idx = torch.utils.data.random_split(
        range(n), [n - val_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    train_ds = Subset(base_ds, list(train_idx))
    val_ds   = Subset(base_val, list(val_idx))

    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                          num_workers=4, pin_memory=True, persistent_workers=True)
    val_dl   = DataLoader(val_ds, batch_size=BATCH_SIZE,
                          num_workers=4, pin_memory=True, persistent_workers=True)

    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(512, 1))

    # ---- Phase A: freeze backbone, train only the head for 3 epochs ----
    for p in model.parameters():
        p.requires_grad = False
    for p in model.fc.parameters():
        p.requires_grad = True
    model = model.to(device)

    opt = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()),
                            lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    best_acc = 0.0
    epochs = 30
    warmup_epochs = 3

    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    for epoch in range(epochs):
        # ---- Phase B: unfreeze everything after warmup, reset optimizer ----
        if epoch == warmup_epochs:
            for p in model.parameters():
                p.requires_grad = True
            opt = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs - warmup_epochs)

        model.train()
        for x, y in train_dl:
            x = x.to(device, non_blocking=True)
            y = y.float().unsqueeze(1).to(device, non_blocking=True)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()

        sched.step()

        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in val_dl:
                x = x.to(device, non_blocking=True)
                y = y.to(device, non_blocking=True)
                pred = (torch.sigmoid(model(x)) > 0.5).float()
                correct += (pred.squeeze() == y).sum().item()
                total += y.numel()
        acc = correct / total
        lr_now = opt.param_groups[0]["lr"]
        tag = "head-only" if epoch < warmup_epochs else "full"
        print(f"epoch {epoch:02d} [{tag}] lr={lr_now:.2e} val_acc={acc:.4f}")

        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), CKPT_DIR / "tampernet_resnet18.pt")
            print(f"  ✓ saved (best={best_acc:.4f})")

    print(f"\nBest val accuracy: {best_acc:.4f}")
    print(f"Checkpoint: {CKPT_DIR / 'tampernet_resnet18.pt'}")


if __name__ == "__main__":
    main()