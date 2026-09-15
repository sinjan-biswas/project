from pathlib import Path
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CKPT = BASE_DIR / "models" / "tampernet" / "tampernet_resnet18.pt"

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class TamperNet:
    def __init__(self, weights: str | Path = DEFAULT_CKPT):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.available = Path(weights).exists()

        if not self.available:
            print(f"[TamperNet] WARNING: checkpoint not found at {weights}. "
                  f"CNN signal will be skipped; ELA-only mode.")
            self.model = None
            return

        self.model = models.resnet18(weights=None)
        self.model.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(512, 1))
        self.model.load_state_dict(torch.load(weights, map_location=self.device))
        self.model.to(self.device).eval()
        self.target_layer = [self.model.layer4[-1]]

        self.tf = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])

    def predict(self, image_path: str, heatmap_out: str | None = None) -> dict:
        if not self.available:
            return {"forgery_probability": 0.0, "heatmap": None, "available": False}

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Could not read image: {image_path}")
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        pil = Image.fromarray(img_rgb)
        inp = self.tf(pil).unsqueeze(0).to(self.device)

        with torch.no_grad():
            prob = torch.sigmoid(self.model(inp)).item()

        heatmap_path = None
        if heatmap_out:
            try:
                from pytorch_grad_cam import GradCAM
                from pytorch_grad_cam.utils.model_targets import BinaryClassifierOutputTarget

                with GradCAM(model=self.model, target_layers=self.target_layer) as cam:
                    grayscale = cam(input_tensor=inp, targets=[BinaryClassifierOutputTarget(0)])[0]
                heatmap = cv2.applyColorMap(np.uint8(255 * grayscale), cv2.COLORMAP_JET)
                heatmap = cv2.resize(heatmap, (img_rgb.shape[1], img_rgb.shape[0]))
                overlay = cv2.addWeighted(img_bgr, 0.6, heatmap, 0.4, 0)
                cv2.imwrite(str(heatmap_out), overlay)
                heatmap_path = str(heatmap_out)
                print(f"[TamperNet] heatmap saved → {heatmap_out}")
            except Exception as e:
                import traceback
                print(f"[TamperNet] Grad-CAM FAILED: {type(e).__name__}: {e}")
                traceback.print_exc()

        return {
            "forgery_probability": float(prob),
            "heatmap": heatmap_path,
            "available": True,
        }