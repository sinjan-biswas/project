# AI Border Screening System

## Overview
AI Border Screening is a local web application for passport or identity-document screening. It combines:

- OCR and MRZ extraction (PaddleOCR)
- Document field validation
- Document classification (passport, PAN card, etc.)
- Image tampering detection (photo substitution, stamp forgery, text manipulation)
- Face verification against a live camera photo (InsightFace)
- Risk scoring with weighted decision engine
- A browser-based screening dashboard

## Project Layout
```text
readme.md
backend/
  main.py                 FastAPI application (v2.2.0)
  pyproject.toml          Python project metadata and dependencies
  requirements.txt        Alternative pip dependency list
  uv.lock                 Locked dependency versions
  services/               OCR, validation, face, tampering, classification services
    ocr_service.py        PaddleOCR wrapper with line extraction
    ocr_engine.py         Low-level OCR engine
    validation_service.py Document field validation rules
    face_service.py       InsightFace embedding + verification
    tampering_service.py  Unified tampering analysis
    document_classifier.py Document type detection
    photo_substitution.py Face swap/morph detection
    stamp_forgery.py      Stamp/seal tampering detection
    text_manipulation.py  Text alteration detection
    preprocess.py         Image preprocessing utilities
    metadata_service.py   EXIF/metadata extraction
    parsers/              MRZ and field parsers
  risk_engine/
    scorer.py             Weighted risk scoring (tampering 35%, face 30%, validation 20%, expiry 15%)
  tampering_dl/           Deep learning tampering models
  training/               Model training scripts
  models/
    insightface/          InsightFace model weights
  data/                   Reference data and test images
  tests/                  Unit and integration tests
  static/                 Static assets
frontend/
  index.html              Web interface
  server.py               Local static-file server
  css/
    styles.css            Interface styles
  js/
    app.js                Browser behavior and API calls
```

## Requirements
- `uv` 0.12 or newer
- Python 3.12 or newer
- Tesseract OCR installed and available on PATH
- A browser with camera access
- Optional: NVIDIA GPU and the GPU ONNX Runtime package for GPU inference

## Setup
1. Install `uv` if it is not already available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install the locked backend dependencies. `uv sync` creates and manages the backend virtual environment automatically:

```bash
cd backend
uv sync
```

3. Install Tesseract OCR if it is not already installed. On Debian or Ubuntu:

```bash
sudo apt update
sudo apt install tesseract-ocr
```

4. (Optional) For GPU acceleration, install the CUDA-enabled ONNX Runtime:

```bash
uv pip install onnxruntime-gpu --extra-index-url https://download.pytorch.org/whl/cu128
```

## Running the Application
Start the API in one terminal from the backend directory:

```bash
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:

`http://localhost:8000`

Start the frontend in a second terminal from the frontend directory:

```bash
cd frontend
uv run --no-project python server.py
```

Open the web interface at:

`http://localhost:3000`

To check that the API is running, open `http://localhost:8000/health`.

## Use the Interface
1. Open the frontend URL in a browser.
2. Upload a passport or identity-document image in JPG, PNG, or WebP format.
3. Start the camera and capture a live face photo.
4. Select the screening action.
5. Review the OCR, validation, tampering, biometric, and risk results.

The browser must be given permission to use the camera. The local frontend uses the API at `http://localhost:8000`.

## API Endpoints

### `GET /health`
Returns an API status check:
```json
{"status":"operational","version":"2.2.0"}
```

### `POST /api/v2/screen`
Accepts multipart form data with these required fields:
- `document`: passport or identity-document image
- `live_photo`: captured face image

The response includes:
- `screening_id`
- `document_type` (passport, pan_card, etc.)
- `ocr_data` (extracted fields, MRZ, confidence scores)
- `validation` (field validation results, expiry check)
- `tampering` (tampering_score, is_tampered, risk_factors)
- `biometrics` (face_distance, match boolean, threshold)
- `risk_assessment` (score, decision: APPROVE/SECONDARY_INSPECTION/DENY, reasons)
- `timestamp`

Example request:
```bash
curl -X POST http://localhost:8000/api/v2/screen \
   -F "document=@/path/to/document.jpg" \
   -F "live_photo=@/path/to/face.jpg"
```

## Key Features

### Document Classification
Automatically detects document type (passport, PAN card, Aadhaar, driver's license, etc.) and routes to appropriate validation rules.

### OCR Pipeline
- PaddleOCR for text detection and recognition
- MRZ (Machine Readable Zone) parsing for passports
- Confidence scoring per field
- Debug mode via `DEBUG_OCR=true` environment variable

### Tampering Detection
Multi-modal analysis combining:
- **Photo substitution**: Face swap/morph detection using embedding consistency
- **Stamp forgery**: Seal/stamp authenticity via texture analysis
- **Text manipulation**: Character-level inconsistency detection
- **Metadata analysis**: EXIF timestamps, software signatures, compression artifacts

### Face Verification
- InsightFace (ArcFace) embeddings
- Cosine distance comparison with configurable threshold
- Liveness cues from capture flow

### Risk Scoring
Weighted decision engine:
| Factor | Weight | Thresholds |
|--------|--------|------------|
| Tampering | 35% | >45% → elevated |
| Face similarity | 30% | >0.55 distance → weak |
| Validation errors | 20% | Any error → full weight |
| Expiry | 15% | Expired → full weight |

Decisions:
- **APPROVE**: score < 30
- **SECONDARY_INSPECTION**: 30 ≤ score ≤ 70
- **DENY**: score > 70

**Hard rule**: Unreadable OCR forces minimum score of 55 (SECONDARY_INSPECTION).

## Configuration
Environment variables:
- `DEBUG_OCR=true` — Include raw OCR lines in response
- `FACE_THRESHOLD` — Cosine distance threshold for face match (default: 0.6)
- `TAMPERING_THRESHOLD` — Tampering score threshold (default: 50)

## Notes
- The API currently allows cross-origin requests for local development.
- Uploaded document bytes are processed temporarily for tampering analysis and the temporary file is removed afterward.
- AI model initialization may take time on the first backend startup.
- Do not use this development configuration directly in production without adding authentication, restricted CORS origins, secure deployment, logging controls, and data-retention safeguards.

## Troubleshooting
- If OCR fails, verify that `tesseract --version` works in the same environment used to start the API.
- If face verification cannot initialize, check that the InsightFace model is available under `backend/models/insightface/`.
- Camera access generally requires a secure browser context. `localhost` is supported by modern browsers.
- For GPU issues, verify `onnxruntime-gpu` is installed and `nvidia-smi` shows available devices.