# AI Border Screening System

A full-stack border screening prototype that combines document OCR, validation, tampering detection, face verification, and risk scoring to assess traveler identity and document authenticity.

## Overview

This project includes:
- A Python FastAPI backend for the screening pipeline
- A lightweight frontend web UI for document upload and camera capture
- Docker-based local orchestration for running the app together
- MRZ-based passport/ID validation and risk assessment logic
- Tampering analysis hooks and a face verification placeholder

## System Architecture

- Backend API: FastAPI service that receives a document and live face image
- OCR + MRZ parsing: extracts text and parses passenger/document metadata
- Validation rules: checks MRZ structure and expiry/data consistency
- Tampering analysis: evaluates document authenticity risk
- Face verification: compares the document and live image
- Risk engine: aggregates factors into an approval / secondary inspection / deny score

## Tech Stack

- Python
- FastAPI
- Uvicorn
- OpenCV
- Tesseract OCR
- fastmrz
- Redis / Celery / SQLAlchemy (present in backend dependencies)
- JavaScript / HTML / CSS frontend
- Docker Compose

## Project Structure

```text
.
├── backend/
│   ├── app/
│   ├── risk_engine/
│   ├── services/
│   ├── tampering-dl/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── server.py
│   ├── js/
│   ├── css/
│   └── Dockerfile
├── tests/
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Features

### Document screening pipeline
The backend endpoint receives:
- document image
- live facial image

It then evaluates:
1. OCR extraction
2. MRZ validation
3. Tampering analysis
4. Face verification
5. Risk scoring

### API endpoint
The primary route is:

- POST /api/v2/screen

Request format:
- document: file upload
- live_photo: file upload

Response includes:
- OCR data
- validation details
- tampering result
- biometric result
- risk assessment
- timestamp

### Health check
- GET /health

## Prerequisites

Before running locally, install:
- Docker and Docker Compose
- Python 3.10+
- Tesseract OCR
- Optional: virtual environment tools such as venv

## Quick Start with Docker

From the project root:

```bash
docker compose up --build
```

This starts:
- backend on http://localhost:8000
- frontend on http://localhost:3000

To stop the services:

```bash
docker compose down
```

## Local Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

The backend will run on:
- http://localhost:8000

## Local Frontend Setup

```bash
cd frontend
python server.py
```

The frontend will run on:
- http://localhost:3000

## Testing

The repository contains a test folder with example checks for OCR and MRZ logic. You can run them from the project root or inside the test directory depending on the current project configuration.

Example:

```bash
cd tests
python run_all_12_tests.py
```

## Notes

- Face verification is currently a stub implementation and should be replaced with a production model such as DeepFace or another biometric matching service.
- OCR relies on Tesseract and expects tessdata to be available in the environment.
- The project is intended as an AI screening prototype and can be extended with real document verification, model integration, and database persistence.

## License

This project is provided as a local development prototype. Add the appropriate license if you plan to distribute or publish it.

## Contributing

If you want to extend the system:
- improve OCR accuracy
- add stronger MRZ validation rules
- replace the stub face verification with a real model
- connect a database and worker queue for production usage
- add authentication and authorization for secure deployment
