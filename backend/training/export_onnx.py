"""Export a trained checkpoint to ONNX for inference with onnxruntime.

Usage:
    python export_onnx.py --checkpoint runs/doccls/best.pt --output-dir ../models/document_classifier
"""

import argparse
import json
import os

import torch
from torchvision import models


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    arch = ckpt["arch"]
    num_classes = ckpt["num_classes"]
    classes = ckpt["classes"]

    if arch == "mobilenet_v3_small":
        model = models.mobilenet_v3_small(weights=None)
        in_features = model.classifier[3].in_features
        model.classifier[3] = torch.nn.Linear(in_features, num_classes)
    else:
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, num_classes)

    model.load_state_dict(ckpt["model_state"])
    model.eval()

    os.makedirs(args.output_dir, exist_ok=True)
    onnx_path = os.path.join(args.output_dir, "document_classifier.onnx")
    labels_path = os.path.join(args.output_dir, "labels.json")

    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        model, dummy, onnx_path,
        input_names=["input"], output_names=["logits"],
        opset_version=18,
    )
    with open(labels_path, "w") as f:
        json.dump(classes, f)

    # verify with onnxruntime
    import onnxruntime as ort
    import numpy as np
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    out = session.run(None, {"input": dummy.numpy().astype("float32")})[0]
    assert out.shape[1] == num_classes, f"unexpected output shape {out.shape}"
    print(f"exported {onnx_path} (output shape {out.shape})")
    print(f"wrote {labels_path}: {classes}")
    print(f"copy both files to backend/models/document_classifier/ in the app repo")


if __name__ == "__main__":
    main()
