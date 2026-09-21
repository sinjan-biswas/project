# AI Border Screening System

A local document and traveler screening application that analyzes identity documents, performs OCR and validation, checks for tampering, verifies the traveler face against a live camera capture, and produces a risk score.

## Features

- Document classification for common ID documents
- OCR and MRZ extraction for document fields
- Validation of document metadata, expiry, and field consistency
- Image quality assessment and enhancement retry flow
- Tampering detection for substitution, stamp manipulation, and text alteration
- Face verification using InsightFace embeddings
- Risk scoring with approval, secondary review, and denial outcomes
- Browser-based UI built with Vite + React

## Project structure

```text
project/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── README.md
│   ├── data/
│   ├── models/
│   ├── risk_engine/
│   ├── services/
│   ├── tampering_dl/
│   ├── tests/
│   └── training/
├── frontend-vite/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── public/
│   └── src/
├── enhancers/
│   ├── AI_enhance/
│   ├── Document-Image-Dewarping/
│   └── Real-ESRGAN/
├── list/
├── readme.md
└── ...
```

## Requirements

- Python 3.11+ or 3.12+
- Node.js 18+ and npm
- Tesseract OCR installed and available on your PATH
- A browser with camera access
- Optional: GPU acceleration support for certain ML workloads

## Setup

### 1) Backend dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you use `uv`, the project also supports:

```bash
cd backend
uv sync
```

### 2) Install Tesseract

On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

### 3) Frontend dependencies

```bash
cd frontend-vite
npm install
```

## Run the application

### Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:

- http://localhost:8000
- health check: http://localhost:8000/health

### Start the frontend

```bash
cd frontend-vite
npm run dev
```

Open the Vite app in the browser at:

- http://localhost:5173

## API usage

### Health check

```bash
curl http://localhost:8000/health
```

### Document screening

```bash
curl -X POST http://localhost:8000/api/v2/screen \
  -F "document=@/path/to/document.jpg" \
  -F "live_photo=@/path/to/live_photo.jpg"
```

The API expects multipart form data with:

- `document`: the ID document image
- `live_photo`: the traveler face image

The response includes OCR results, validation details, tampering analysis, biometrics, and a risk assessment.

## Screening flow

1. Upload the document image.
2. The backend checks image quality and may attempt enhancement.
3. OCR extracts text and MRZ data.
4. Validation rules check field consistency and expiry.
5. The tampering detector analyzes image integrity.
6. Face verification compares the document photo to the live capture.
7. The risk engine decides between approve, secondary inspection, or deny.

## Notes

- This is intended for local development and demo usage.
- CORS is intentionally permissive for local testing.
- Camera access requires browser permission.
- Model initialization may take some time on the first run.
- Do not treat this as production-ready security infrastructure without additional authentication, logging, and deployment hardening.

## Troubleshooting

- If OCR fails, confirm Tesseract is installed and reachable from the same environment as the backend.
- If the API cannot initialize face verification, check the model files under `backend/models/insightface/`.
- If the frontend cannot reach the backend, confirm the backend is running on port 8000 and the app is using the correct API base URL.
- For GPU-related issues, verify the required CUDA runtime dependencies are installed.
