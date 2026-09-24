#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CUDA_INDEX="https://download.pytorch.org/whl/cu130"

echo "==> backend (python 3.12)"
cd backend
[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt \
  --extra-index-url "$CUDA_INDEX"
cd ..

echo "==> AI_enhance (python 3.12)"
cd enhancers/AI_enhance
[ -d venv ] || uv venv --python 3.12 venv
uv pip install --python venv/bin/python -r requirements.lock.txt
cd ../..

echo "==> Real-ESRGAN (python 3.10)"
cd enhancers/Real-ESRGAN
uv python install 3.10
[ -d venv ] || uv venv --python 3.10 venv
uv pip install --python venv/bin/python -r requirements.lock.txt \
  --extra-index-url "$CUDA_INDEX"
uv pip install --python venv/bin/python -e . --no-deps

# functional_tensor shim (torchvision >= 0.17)
cat > venv/lib/python3.10/site-packages/torchvision/transforms/functional_tensor.py <<'SHIM'
"""Back-compat shim: torchvision >= 0.17 removed this module."""
from torchvision.transforms.functional import rgb_to_grayscale as _rgb_to_grayscale


def rgb_to_grayscale(img, num_output_channels=1):
    if img.dim() == 3:
        return _rgb_to_grayscale(img.unsqueeze(0), num_output_channels).squeeze(0)
    return _rgb_to_grayscale(img, num_output_channels)
SHIM
cd ../..

echo "==> Document-Image-Dewarping (python 3.10, mmcv-full 1.7.1)"
cd enhancers/Document-Image-Dewarping
uv python install 3.10
[ -d venv ] || uv venv --python 3.10 venv
uv pip install --python venv/bin/python -r requirements.lock.txt
# mmcv-full is not on PyPI — install from openmmlab index
uv pip install --python venv/bin/python mmcv-full==1.7.1 \
  -f https://download.openmmlab.com/mmcv/dist/cu117/torch1.13/index.html
cd ../..

echo
echo "==> Verifying imports"
backend/.venv/bin/python        -c "import fastapi, uvicorn; print('  backend ok')"
enhancers/AI_enhance/venv/bin/python -c "from zero_dce import ZeroDCE; print('  ai_enhance ok')"
enhancers/Real-ESRGAN/venv/bin/python -c "from basicsr.archs.rrdbnet_arch import RRDBNet; print('  realesrgan ok')"
enhancers/Document-Image-Dewarping/venv/bin/python -c "import torch, mmcv; print('  dewarp ok', torch.__version__, mmcv.__version__)"

echo
echo "All four venvs ready."
