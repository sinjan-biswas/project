"""Print per-split, per-class image counts.

Usage:
    python -m training.check_dataset
    python -m training.check_dataset --data data
"""
import argparse
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def count_images(folder: Path) -> int:
    return sum(1 for p in folder.rglob("*") if p.suffix.lower() in IMG_EXTS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    args = ap.parse_args()

    root = Path(args.data)
    for split in ("train", "valid"):
        split_dir = root / split
        if not split_dir.is_dir():
            print(f"[missing] {split_dir}")
            continue

        print(f"\n=== {split} ===")
        classes = sorted(p for p in split_dir.iterdir() if p.is_dir())
        total = 0
        for c in classes:
            n = count_images(c)
            total += n
            bar = "█" * min(50, n // 5)
            print(f"  {c.name:<18} {n:>5}  {bar}")
        print(f"  {'TOTAL':<18} {total:>5}")

    # Warnings
    print()
    for split in ("train", "valid"):
        others = root / split / "others"
        if others.is_dir() and count_images(others) < 100:
            print(f"⚠  {split}/others has < 100 images — "
                  f"expect false positives on junk inputs.")


if __name__ == "__main__":
    main()