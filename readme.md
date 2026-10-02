# AI-Based Fake Identity & Document Screening System

<div align="center">

📌 **Version 3.0.0** | 🐍 Python 3.12+ | 🌐 Node.js 18+ | 🏛️ Hyperledger Fabric

🔍 **3-Stage Verification Process**

📄 **Document Upload** → 🔍 **OCR & Validation** → 👤 **Liveness Check** → 🏛️ **Blockchain Record**

📌 **MIT License**

</div>

--- 

## 🌟 Overview

This system verifies identity documents (passports, visas, Aadhaar, PAN cards, driving licenses, voter IDs, permits) through a **3-stage guided flow** with a hard liveness check, then records every decision on a **Hyperledger Fabric** blockchain ledger.

### 🎯 Key Features

✅ **Automated Document Classification** - Identifies 7+ document types
✅ **Tampering Detection** - 5-signal fusion (CNN, photo swap, text, stamps, EXIF)
✅ **Liveness Verification** - Blink challenge + anti-spoof + face matching
✅ **Blockchain Integration** - Immutable record keeping with private data collection
✅ **GDPR-Compliant** - Private data collection for sensitive information

📊 **Performance**: 5-7 seconds per screening (GPU), 15-20 seconds without GPU

--- 

## Overview

The system verifies identity documents (passports, visas, Aadhaar, PAN, driving licences, voter IDs, permits) through a **3-stage guided flow** with a hard liveness gate, then records every decision on a **Hyperledger Fabric** ledger.

### Key Features

- **5–7 s per screening** (GPU), **15–20 s** without GPU
- **7 document types** classified automatically
- **5-signal tampering fusion** (CNN + photo swap + text + stamps + EXIF metadata)
- **Blink + anti-spoof + face-match** liveness pipeline
- **CouchDB-backed** rich query for the audit history view
- **Private data collection** for GDPR-compliant PII storage

--- 

## 🚀 3-Stage Verification Process

### 📄 Stage 1: Document Upload & Classification

**Endpoint:** `POST /api/v2/documents/validate`

📌 **Purpose:** Upload and validate document quality

🔹 **Input:** 1-10 images (JPEG/PNG/WebP, ≤15MB each)

🔹 **Output:**
- Document quality assessment
- Document type classification
- Enhanced preview images
- Session ID for next stage

📊 **Example Response:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "files": [
    {
      "filename": "passport.jpg",
      "quality": { "decision": "enhance", "score": 72.5 },
      "classification": { "doc_type": "passport", "confidence": 0.968 }
    }
  ]
}
```

### 🔍 Stage 2: OCR & Document Validation

**Endpoint:** `POST /api/v2/documents/details`

📌 **Purpose:** Extract text and validate document content

🔹 **Input:** Session ID from Stage 1

🔹 **Output:**
- Extracted document fields (name, passport number, etc.)
- Machine Readable Zone (MRZ) data
- Validation status (errors/warnings)

📊 **Example Response:**
```json
{
  "documents": [
    {
      "doc_type": "passport",
      "fields": {"name": "John Doe", "passport_number": "ABC123"},
      "validation": {"valid": true, "errors": []}
    }
  ]
}
```

### 👤 Stage 3: Liveness Verification

**Endpoints:**
- `POST /api/v2/screening/start-liveness` - Initiate liveness check
- `POST /liveness/session` - Upload document photo for liveness
- `POST /liveness/session/{id}/frame` - Submit webcam frames
- `POST /liveness/session/{id}/verify` - Complete verification

📌 **Purpose:** Verify the person's identity through liveness checks

🔹 **Process:**
1. Blink challenge (genuine eye movement)
2. Anti-spoof detection (MiniFASNetV2)
3. Face matching (biometric verification)

📊 **Example Response:**
```json
{
  "liveness_session_id": "livesess_123",
  "blink_target": 2
}
```

### 🏛️ Finalization & Blockchain Recording

**Endpoint:** `POST /api/v2/screening/finalize`

📌 **Purpose:** Combine all results and record on blockchain

🔹 **Output:**
- Risk assessment (score, decision)
- Tampering detection results
- Liveness verification status
- Blockchain transaction ID
- Fraud alerts (if any)

📊 **Example Response:**
```json
{
  "decision": "APPROVE",
  "risk_score": 22.5,
  "blockchain": {"screening_id": "txid_123"},
  "fraud_alerts": []
}
```

🔹 **Session Management:**
- All sessions expire after 30 minutes
- Frontend shows one stage at a time
- Backend maintains session state in Redis

--- 

## 🏗️ System Architecture

### 🌐 Frontend Components

📌 **Framework:** React 19 + Vite 6 + Tailwind CSS

🔹 **Key Components:**
- **Marketing Sections:** Hero, Pipeline, Signals
- **Wizard Flow:** Step-by-step document verification
- **Screening History:** Real-time ledger updates
- **UI Components:** Step1Upload, Step2Liveness, Step3Results

📊 **Tech Stack:**
- **Frontend:** React 19, Vite 6, Tailwind CSS
- **State Management:** React Context + URL params
- **API Proxy:** Vite proxy for /api/* and /liveness/* endpoints

### 🏢 Backend Components

📌 **Framework:** FastAPI + Uvicorn

🔹 **Key Modules:**

| Module                | Purpose                                                                 |
|-----------------------|-------------------------------------------------------------------------|
| documents.py          | Stage 1 & 2: Document upload, quality, classification, OCR          |
| liveness.py           | Stage 3: Blink challenge, anti-spoof, face matching                    |
| screening_finalize.py | Finalize screening, risk assessment, blockchain recording          |
| screening_history.py | Query Fabric ledger for screening history                            |
| DocumentPipeline      | Core processing pipeline: Quality → Enhance → OCR → Validation → Tampering → Face → Risk → Blockchain |

🔹 **Models:**
- PaddleOCR + TrOCR for text extraction
- InsightFace for face matching
- MiniFASNetV2 for anti-spoof detection
- TamperNet for tampering detection

🔹 **Infrastructure:**
- **Session Management:** Redis (metadata) + local disk (raw bytes)
- **Enhancers:** Warm subprocesses on ports 8765 (dewarping) and 8766 (super-resolution)
- **Rate Limiting:** Per-IP and per-session

### 🏛️ Blockchain Integration

📌 **Framework:** Hyperledger Fabric 2.5

🔹 **Channel:** screening-channel

🔹 **Chaincode:** screening v1.0 (Go)

🔹 **Key Functions:**
- RecordScreening: Store screening results
- GetScreening: Retrieve screening details
- GetScreeningPII: Access private personal data
- QueryScreeningsByCheckpoint: Search by travel checkpoint
- QueryScreeningsByPassport: Search by passport number
- CheckIdentityReuse: Detect duplicate identities
- CheckImpossibleTravel: Detect travel pattern anomalies
- GetAlert: Retrieve fraud alerts
- GetAlertsByPassport: Get alerts for specific passport
- runFraudChecks: Run fraud detection algorithms

🔹 **Data Storage:**
- **State DB:** CouchDB (required for rich queries)
- **Private Data Collection:** screeningPrivateDetails (blockToLive: 90 days)

📊 **Blockchain Features:**
- Immutable record keeping
- Private data collection for GDPR compliance
- Rich query capabilities through CouchDB 

## 🛠️ Technology Stack

### 📌 Core Components

| Component       | Technology                     | Purpose                                                                 |
|----------------|-------------------------------|----------------------------------------------------------------------|
| Frontend       | React 19, Vite 6, Tailwind CSS | User interface with step-by-step wizard flow                        |
| Backend        | FastAPI, Uvicorn, Python 3.12  | REST API server with session management and processing pipeline     |
| ML/CV          | PyTorch, PaddleOCR, TrOCR, InsightFace, ONNX Runtime | Machine learning models for document processing and verification |
| Blockchain     | Hyperledger Fabric 2.5, Go Chaincode | Immutable ledger for storing screening results                        |
| Database       | Redis, CouchDB                 | Session management and ledger state storage                           |
| Infrastructure | Docker 24.0.9, docker-compose 2.24.5 | Containerized deployment of Fabric network                         |

### 📌 Additional Features

| Feature                | Technology/Implementation      | Purpose                                                                 |
|------------------------|----------------------------------|----------------------------------------------------------------------|
| Health Check           | FastAPI /health endpoint       | System status monitoring                                            |
| Rate Limiting          | FastAPI middleware               | Prevent abuse and ensure fair usage                                 |
| Session Management     | Redis (30-min TTL)               | Maintain user sessions across stages                                 |
| Private Data Collection | Hyperledger Fabric Private Data   | GDPR-compliant storage of sensitive personal information              |
| Warm Servers           | Subprocesses on ports 8765/8766  | Pre-warm document enhancement services for faster response times     |

### 📌 Supported Document Types

📄 Passports
📄 Visas
📄 Aadhaar Cards
📄 PAN Cards
📄 Driving Licenses
📄 Voter IDs
📄 Permits

--- 

## 🚀 Quick Start Guide

### 📌 Prerequisites

✅ Docker 24.0.9
✅ Docker Compose 2.24.5
✅ Python 3.12
✅ Node.js 18+
✅ Redis

### 🛠️ Step 1: Set Up Hyperledger Fabric

```bash
# Navigate to Fabric test network
cd ~/Documents/project/fabric-samples/test-network

# Set environment variables
export PATH="$HOME/Documents/project/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="$HOME/Documents/project/fabric-samples/config"

# First time setup (creates channel and deploys chaincode)
./network.sh down
./network.sh up createChannel -c screening-channel -s couchdb
./network.sh deployCC \
  -c screening-channel -ccn screening \
  -ccp ~/Documents/project/fabric-samples/screening-chaincode-go \
  -ccl go -ccv 1.0 -ccs 1 \
  -cccg ~/Documents/project/fabric-samples/screening-chaincode-go/collections_config.json
```

🔹 **Subsequent boots (after first setup):**
```bash
docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com \
              couchdb0 couchdb1 cli
```

### 📊 Step 2: Start Redis

```bash
# Check if Redis is running
redis-cli ping

# If not running, start Redis service
sudo systemctl start redis-server
```

### 🐍 Step 3: Start Backend Server

```bash
# Verify peer is in PATH
which peer

# Navigate to backend directory
cd ~/Documents/project/backend

# Start FastAPI server
uvicorn main:app --port 8000 --reload

# Wait for startup message: "Application startup complete."
```

### 🌐 Step 4: Start Frontend

```bash
# Navigate to frontend directory
cd ~/Documents/project/frontend-vite

# Install dependencies (first time only)
pm install

# Start development server
npm run dev
```

### 🔍 Access the Application

Open your browser to:
🌐 [http://localhost:5173](http://localhost:5173)

📌 **Expected to see:**
- Welcome screen with system overview
- Step-by-step document verification wizard
- Screening history dashboard

--- 

## 🔧 API Reference

### 📌 Overview

The API follows a **3-stage verification process** with clear endpoints for each stage. All endpoints return appropriate HTTP status codes and JSON responses.

### 📄 Stage 1: Document Upload & Classification

**Endpoint:** `POST /api/v2/documents/validate`

📌 **Purpose:** Upload and validate document quality

📊 **Request:**
```http
POST /api/v2/documents/validate
Content-Type: multipart/form-data

files: <binary>[]   # 1-10 images (JPEG/PNG/WebP, ≤15MB each)
```

📊 **Response:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "expires_at": 1790394084.97,
  "blocked": false,
  "files": [
    {
      "index": 0,
      "filename": "passport.jpg",
      "quality": {
        "decision": "enhance",
        "score": 72.5,
        "reasons": ["tilted 12°"]
      },
      "classification": {
        "doc_type": "passport",
        "confidence": 0.968
      },
      "enhanced": true,
      "preview_url": "/api/v2/documents/preview/sess_.../0"
    }
  ]
}
```

### 🔍 Stage 2: OCR & Document Validation

**Endpoint:** `POST /api/v2/documents/details`

📌 **Purpose:** Extract text and validate document content

📊 **Request:**
```http
POST /api/v2/documents/details
Content-Type: application/json

{ "session_id": "sess_a1b2c3d4e5f6" }
```

📊 **Response:**
```json
{
  "documents": [
    {
      "index": 0,
      "doc_type": "passport",
      "fields": {
        "name": "John Doe",
        "passport_number": "ABC12345",
        "date_of_birth": "1980-01-01"
      },
      "mrz": {
        "raw": ["P<INDJohnDoe19800101M1234567890>ABCDEF1234567890"]
      },
      "validation": {
        "valid": true,
        "errors": [],
        "warnings": []
      },
      "ocr_failed": false
    }
  ]
}
```

### 👤 Stage 3: Liveness Verification

**Endpoint:** `POST /api/v2/screening/start-liveness`

📌 **Purpose:** Initiate liveness verification process

📊 **Request:**
```http
POST /api/v2/screening/start-liveness
Content-Type: application/json

{ "session_id": "sess_123", "doc_index": 0 }
```

📊 **Response:**
```json
{
  "liveness_session_id": "live_456",
  "blink_target": 2
}
```

### 🎥 Liveness Verification Endpoints

📌 **Create Liveness Session:**
```http
POST /liveness/session
Content-Type: multipart/form-data

document_photo: <binary>  # JPEG/PNG/WebP, ≤15MB
```

📌 **Submit Webcam Frames:**
```http
POST /liveness/session/{id}/frame
Content-Type: multipart/form-data

frame: <binary>  # JPEG/PNG/WebP, ≤15MB
client_timestamp: float
```

📌 **Complete Verification:**
```http
POST /liveness/session/{id}/verify
→ {"verified": true, "verification_id": "JWT", "state": "verified"}
```

📌 **Check Status:**
```http
GET /liveness/session/{id}/status
```

### 🏛️ Finalize Screening

**Endpoint:** `POST /api/v2/screening/finalize`

📌 **Purpose:** Combine all results and record on blockchain

📊 **Request:**
```http
POST /api/v2/screening/finalize
Content-Type: application/json

{ "screening_session_id": "sess_123", "liveness_session_id": "live_456" }
```

📊 **Response:**
```json
{
  "decision": "APPROVE",
  "risk_score": 22.5,
  "liveness": {
    "blink_count": 2,
    "anti_spoof": {
      "passed": true,
      "score": 0.99
    },
    "face_match": {
      "passed": true,
      "distance": 0.48
    }
  },
  "tampering": [
    {
      "index": 0,
      "tampering_score": 8.2,
      "is_tampered": false
    }
  ],
  "validation_summary": {
    "expired": false,
    "errors": []
  },
  "risk_assessment": {
    "score": 22.5,
    "decision": "APPROVE",
    "reasons": []
  },
  "blockchain": {
    "screening_id": "txid_789",
    "recorded": true
  },
  "fraud_alerts": []
}
```

### 📊 Screening History

📌 **Search by Checkpoint:**
```http
GET /api/v2/history?checkpoint=JFK_01&limit=50
```

📌 **Get Specific Screening:**
```http
GET /api/v2/history/{screening_id}
```

📌 **Get Screening State:**
```http
GET /api/v2/screening/{screening_session_id}/state
```

### 🛡️ Health Check

**Endpoint:** `GET /health`

📌 **Purpose:** Check system health status

📊 **Response:**
```json
{
  "status": "operational",
  "version": "3.0.0"
}
```

### ⚠️ Legacy Endpoint (Deprecated)

**Endpoint:** `POST /api/v2/screen`

📌 **Note:** This endpoint is deprecated but still works for backward compatibility.

📊 **Request:**
```http
POST /api/v2/screen
Content-Type: multipart/form-data

document: <binary>
live_photo: <binary>
```

--- 

## 🔧 Configuration

### 📌 Risk Assessment Thresholds

📊 **Decision Bands:**

| Score Range       | Decision                     | Notes                                                                 |
|-------------------|-----------------------------|----------------------------------------------------------------------|
| < 30              | APPROVE                      | Low risk, but enhanced images get secondary inspection              |
| 30–70             | SECONDARY_INSPECTION          | Medium risk, requires manual review                                |
| > 70              | DENY                         | High risk, automatic rejection                                      |

📌 **Technical Thresholds:**

| Threshold Type          | Value | Description                                                                 |
|-----------------------|-------|-----------------------------------------------------------------------------|
| APPROVE_THRESHOLD     | 30    | Maximum score for automatic APPROVE decision                           |
| DENY_THRESHOLD         | 70    | Minimum score for automatic DENY decision                             |
| FACE_THRESHOLD        | 0.55  | Cosine similarity floor for face matching success                       |
| Anti-Spoof Threshold   | 0.5   | MiniFASNetV2 live-class threshold (0.5 = live, >0.5 = spoof suspected) |

### 🌍 Environment Variables

📌 **Fabric Configuration:**

```bash
export FABRIC_CFG_PATH="$HOME/Documents/project/fabric-samples/config"
export PATH="$HOME/Documents/project/fabric-samples/bin:$PATH"
```

📌 **Optional Environment Variables:**

```bash
export DEBUG_OCR=true                # Include raw OCR lines in API responses

export CUDA_VISIBLE_DEVICES=0          # Pin to specific GPU for CUDA acceleration
```

📌 **Backend Configuration:**

The backend reads `REDIS_URL` from `backend/app/config.py` for Redis connection settings.

--- 

## ⚠️ Known Limitations & Mitigations

### 🔍 Anti-Spoof Detection (PAD)

📌 **Limitation:**

`MiniFASNetV2` was trained on pre-2018 datasets (CASIA-FASD, Replay-Attack). It effectively detects:
- Printed photos
- Low-resolution screen replays

However, it **misses modern OLED/high-DPI video replays** when the webcam captures the screen from an angle.

📌 **Mitigations:**

✅ **Blink Challenge:** Requires genuine eye movement to verify liveness
✅ **Face Matching:** Enforces biometric identity verification
✅ **No False Positives:** Removed incorrect reference to non-existent `services/screen_detector.py`

### 🏛️ Blockchain Durability

📌 **Limitation:**

The `network.sh down` command deletes all Docker volumes, **resulting in loss of all ledger records**. There is no automated backup mechanism.

📌 **Mitigation:**

🔹 Treat this setup as a **development/demo environment only**
🔹 For production, implement regular backups of Docker volumes
🔹 Consider using persistent storage for production deployments

### 🔒 Security

📌 **Limitation:**

The FastAPI backend is currently **unauthenticated** (no API keys, no rate limiting).

📌 **Mitigation:**

✅ **Development:** Fine for local testing
✅ **Production:** Requires an API gateway with:
- Authentication (JWT/OAuth)
- Rate limiting
- Request validation

### 🕒 Session Management

📌 **Limitation:**

- Screening sessions expire after **30 minutes** (Redis TTL)
- Liveness sessions share the same TTL
- Stale sessions are automatically swept from disk

📌 **Mitigation:**

✅ **User Experience:** Frontend shows appropriate expiration warnings
✅ **Backend:** `screening_session_store.sweep_stale()` handles cleanup

--- 

## 📂 Project Structure

### 📌 Overview

The project follows a modular architecture with clear separation of concerns between frontend, backend, and blockchain components.

### 🖥️ Backend Structure

📌 **Core Files:**

| File/Folder               | Purpose                                                                 |
|---------------------------|-------------------------------------------------------------------------|
| `main.py`                 | FastAPI application entry point and lifespan management              |
| `app/routers/`            | API route handlers for all stages                                      |
| `app/core/`               | Core utilities and infrastructure                                       |
| `app/services/`           | Business logic and processing services                                 |
| `risk_engine/scorer.py`  | Risk assessment and decision logic                                    |
| `blockchain/client.py`   | Fabric client wrapper for blockchain operations                       |
| `models/`                 | Pre-trained ML models and weights                                        |
| `tampering_dl/`           | Tampering detection models                                              |
| `training/`               | Training scripts and data preparation                                   |

### 📊 Backend Modules

📌 **Router Modules:**

| Module                  | Responsibility                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| `documents.py`         | Stage 1 & 2: Document upload, quality assessment, classification, OCR     |
| `liveness.py`           | Stage 3: Blink challenge, anti-spoof detection, face matching              |
| `screening_finalize.py`| Finalize screening, risk assessment, blockchain recording                |
| `screening_history.py` | Query Fabric ledger for screening history                                |

📌 **Core Services:**

| Service                  | Responsibility                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| `anti_spoof.py`         | MiniFASNetV2 live-class detection                                        |
| `face_match.py`         | Face verification using InsightFace                                      |
| `liveness.py`           | Liveness session management                                              |
| `document_classifier.py`| Document type classification using CNN                                    |
| `tampering_service.py`  | 5-signal tampering detection (CNN + photo swap + text + stamps + EXIF) |
| `validation_service.py`| Document validation and MRZ parsing                                       |

### 🌐 Frontend Structure

📌 **Key Components:**

| Component               | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `index.html`           | Main HTML entry point                                                 |
| `package.json`         | Project dependencies and scripts                                       |
| `src/components/`      | React components for the application UI                               |
| `src/wizard/`          | Step-by-step wizard components (Step1Upload, Step2Liveness, Step3Results) |
| `src/api/client.js`    | API client wrapper for backend communication                            |

### 🏛️ Blockchain Structure

📌 **Fabric Components:**

| Component               | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `test-network/`        | Fabric network orchestration and configuration                        |
| `screening-chaincode-go/` | Go chaincode for screening operations                                  |
| `collections_config.json` | Private data collection configuration for PII storage                  |

### 🔧 Enhancers

📌 **Document Enhancement Services:**

| Service                | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `AI_enhance/`          | Zero-DCE (Document Content Enhancement)                                |
| `Real-ESRGAN/`         | Super-resolution enhancement (warm on port 8766)                        |
| `Document-Image-Dewarping/` | Perspective correction (warm on port 8765)                          |

### 📄 Documentation

| File                   | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `docker.md`            | Detailed Fabric setup and reproducible deployment instructions         |
| `readme.md`            | This project documentation                                              |

### 📌 Key Notes

✅ **Modular Design:** Clear separation between frontend, backend, and blockchain
✅ **Enhancer Services:** Warm subprocesses for document enhancement
✅ **Private Data:** GDPR-compliant private data collection in Fabric
✅ **Session Management:** Redis-backed sessions with 30-minute TTL

--- 

## 🚀 Roadmap

### 📌 Planned Improvements

🔹 **Enhanced User Experience:**

- [ ] **Auto-refresh Screening History** after finalize to show real-time updates
- [ ] **PDF Audit Certificate Export** for compliance and record-keeping

🔹 **Improved Security:**

- [ ] **Stronger PAD Model** (AENet / DeepPixBiS) for better anti-spoof detection
- [ ] **Authentication & Rate Limiting** for production deployment

🔹 **Infrastructure Improvements:**

- [ ] **Docker Compose for App Tier** to simplify backend + frontend + Redis deployment
- [ ] **nginx Reverse Proxy with TLS** for secure single-origin deployment

🔹 **Blockchain Enhancements:**

- [ ] **Persistent Ledger Volumes** to survive `network.sh down` commands
- [ ] **Backup Mechanism** for ledger records in production environments

🔹 **Performance Optimizations:**

- [ ] **Enhanced Warm Server Management** for faster startup times
- [ ] **Optimized Model Loading** for reduced latency

### 📌 Future Directions

🔹 **Multi-language Support** for document processing
🔹 **Mobile Application** for on-the-go document verification
🔹 **Integration with Identity Providers** for seamless authentication
🔹 **Advanced Analytics Dashboard** for screening trends and fraud patterns

--- 

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

--- 

## 🙏 Acknowledgments

### 📌 Core Technologies

This system is built on:

🔹 **Backend:** FastAPI, Uvicorn, Python 3.12
🔹 **Frontend:** React 19, Vite 6, Tailwind CSS
🔹 **Machine Learning:** PyTorch, PaddleOCR, TrOCR, InsightFace
🔹 **Blockchain:** Hyperledger Fabric 2.5
🔹 **Databases:** Redis, CouchDB

### 📊 Training Data

🔹 **Tampering Detection:** CASIA v2 dataset
🔹 **Face Matching:** InsightFace buffalo_l model
🔹 **Document Classification:** Custom-trained CNN models

### 🙌 Special Thanks

We would like to acknowledge the contributions of:

🔹 The Hyperledger community for Fabric development
🔹 The PaddleOCR team for their open-source OCR solutions
🔹 The InsightFace team for their face recognition models
🔹 The CASIA research group for their tampering detection datasets

--- 

## 📌 Contact Information

For questions or feedback, please contact:

📧 sinjanbiswas1024@gmail.com

🔹 **GitHub:** [Your GitHub Profile](https://github.com/yourusername)

🔹 **Project Website:** [Your Project Website](https://yourprojectwebsite.com)