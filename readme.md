# AI Border Screening System

## Overview
AI Border Screening is a local web application for passport or identity-document screening. It combines:

- OCR and MRZ extraction
- Document field validation
- Image tampering detection
- Face verification against a live camera photo
- Risk scoring
- A browser-based screening dashboard

## Project Layout
```text
readme.md
backend/
  main.py                 FastAPI application
  pyproject.toml          Python project metadata and dependencies
  requirements.txt        Alternative pip dependency list
  services/               OCR, validation, face, and tampering services
  risk_engine/            Risk scoring logic
frontend/
  index.html              Web interface
  server.py               Local static-file server
  css/                    Interface styles
  js/                     Browser behavior and API calls
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
2. Upload a passport or identity-document image in JPG or PNG format.
3. Start the camera and capture a live face photo.
4. Select the screening action.
5. Review the OCR, validation, tampering, biometric, and risk results.

The browser must be given permission to use the camera. The local frontend uses the API at
http://localhost:8000.

## API Endpoints
### `GET /health`

Returns an API status check:

```json
{"status":"operational","version":"2.0.0"}
```

### `POST /api/v2/screen`

Accepts multipart form data with these required fields:

- document: passport or identity-document image
- live_photo: captured face image

The response includes:

- screening_id
- ocr_data
- validation
- tampering
- biometrics
- risk_assessment
- timestamp

Example request:

```bash
curl -X POST http://localhost:8000/api/v2/screen \
   -F "document=@/path/to/document.jpg" \
   -F "live_photo=@/path/to/face.jpg"
```

## Notes
- The API currently allows cross-origin requests for local development.
- Uploaded document bytes are processed temporarily for tampering analysis and the temporary file is removed afterward.
- AI model initialization may take time on the first backend startup.
- Do not use this development configuration directly in production without adding authentication, restricted CORS origins, secure deployment, logging controls, and data-retention safeguards.

## Troubleshooting
- If OCR fails, verify that `tesseract --version` works in the same environment used to start the API.
- If face verification cannot initialize, check that the InsightFace model is available under `backend/models/insightface/`.
- Camera access generally requires a secure browser context. `localhost` is supported by modern browsers.
