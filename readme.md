```markdown
# AI-Based Fake Identity & Document Screening System

<div align="center">

![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)
![Node.js](https://img.shields.io/badge/node.js-18+-green.svg)
![Blockchain](https://img.shields.io/badge/blockchain-Hyperledger%20Fabric-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**3-stage guided wizard for document verification, tampering detection, and traveler screening.**

[Quick Start](#-quick-start) • [3-Stage Flow](#-the-3-stage-flow) • [Architecture](#-architecture) • [API](#-api-reference) • [Blockchain](#-blockchain-setup)

</div>

---

## Overview

The system verifies identity documents (passports, visas, Aadhaar, PAN, driving licences, voter IDs, permits) through a **3-stage guided flow** with a hard liveness gate, then records every decision on a **Hyperledger Fabric** ledger.

- **5–7 s per screening** (GPU), **15–20 s** without GPU
- **7 document types** classified automatically
- **5-signal tampering fusion** (CNN + photo swap + text + stamps + EXIF)
- **Blink + anti-spoof + face-match** liveness pipeline
- **CouchDB-backed** rich query for the audit history view
- **Private data collection** for GDPR-compliant PII storage

---

## The 3-Stage Flow

```
┌──────────────────────────┐
│ STAGE 1 · Upload         │  POST /api/v2/documents/validate
│ Quality + Enhance +      │  → per-file: quality, doc_type, confidence
│ Classify                 │  → returns screening_session_id
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│ STAGE 2 · Read           │  POST /api/v2/documents/details
│ OCR + MRZ + Validation   │  → per-doc: fields, MRZ, validation errors
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│ STAGE 3 · Liveness       │  POST /api/v2/screening/start-liveness
│ Blink → PAD → Face match │  POST /liveness/session/{id}/frame (×N)
│                          │  POST /liveness/session/{id}/complete-blink-challenge
│                          │  POST /liveness/session/{id}/anti-spoof
│                          │  POST /liveness/session/{id}/face-match
│                          │  POST /liveness/session/{id}/verify
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│ FINALIZE (automatic)     │  POST /api/v2/screening/finalize
│ Tampering + Risk +       │  → risk_score, decision, tampering[],
│ Blockchain               │    liveness{}, blockchain{}
└──────────────────────────┘
```

Each stage is a discrete user checkpoint. The frontend is a wizard that shows one stage at a time; the backend keeps the session alive in Redis with a 30-minute sliding TTL.

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│  Frontend — React 19 + Vite 6 + Tailwind 3             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Marketing sections (Hero, Pipeline, Signals)    │  │
│  │ Wizard (Step1Upload → Step2Liveness → Step3Res) │  │
│  │ ScreeningHistory (live from Fabric ledger)      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────┬──────────────────────────────┘
                          │ /api/* + /liveness/* (Vite proxy)
┌─────────────────────────▼──────────────────────────────┐
│  Backend — FastAPI + Uvicorn                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Router layer                                     │  │
│  │  documents.py     → stage 1 + 2                  │  │
│  │  liveness.py      → blink / PAD / face match     │  │
│  │  screening_finalize.py → start-liveness + finalize│ │
│  │  screening_history.py  → ledger read-throughs    │  │
│  │  (legacy /api/v2/screen still mounted, deprecated)│ │
│  ├──────────────────────────────────────────────────┤  │
│  │ DocumentPipeline.run_document()                  │  │
│  │  Quality → Enhance → OCR → Validation →          │  │
│  │  Tampering → Face → Risk → Blockchain            │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ Models (lazy singletons)                         │  │
│  │  PaddleOCR + TrOCR · EfficientNet-B0             │  │
│  │  InsightFace buffalo_l · TamperNet ResNet18      │  │
│  │  MiniFASNetV2 (PAD)                              │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  SessionStore — Redis (metadata) + disk (raw bytes)    │
│  Enhancer services — warm subprocesses on :8765/:8766  │
└─────────────────────────┬──────────────────────────────┘
                          │ `peer chaincode invoke` (subprocess)
┌─────────────────────────▼──────────────────────────────┐
│  Hyperledger Fabric 2.5 (Docker)                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Channel: screening-channel                       │  │
│  │ Chaincode: screening v1.0                        │  │
│  │   RecordScreening · GetScreening ·               │  │
│  │   GetScreeningPII · QueryScreeningsByCheckpoint  │  │
│  │                                                  │  │
│  │ Private data collection:                         │  │
│  │   screeningPrivateDetails (blockToLive: 90)      │  │
│  │                                                  │  │
│  │ State DB: CouchDB (required for rich queries)    │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React 19, Vite 6, Tailwind 3, lucide-react | Pure SPA |
| Backend | FastAPI, Uvicorn, Python 3.12 | Session-backed staging |
| ML / CV | PyTorch, PaddleOCR, TrOCR, InsightFace, ONNX Runtime | GPU-optional |
| Sessions | Redis (metadata) + local disk (bytes) | 30-min sliding TTL |
| Blockchain | Hyperledger Fabric 2.5, Go chaincode | CouchDB state store |
| Infra | Docker 24.0.9, docker-compose 2.24.5 | Fabric containers only |

---

## Quick Start

### 1. Start Fabric

```bash
cd ~/Documents/project/fabric-samples/test-network
export PATH="$HOME/Documents/project/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="$HOME/Documents/project/fabric-samples/config"

# First time only — full bring-up
./network.sh down
./network.sh up createChannel -c screening-channel -s couchdb
./network.sh deployCC \
  -c screening-channel -ccn screening \
  -ccp ~/Documents/project/fabric-samples/screening-chaincode-go \
  -ccl go -ccv 1.0 -ccs 1 \
  -cccg ~/Documents/project/fabric-samples/screening-chaincode-go/collections_config.json
```

**Every subsequent boot** (containers exist, just stopped):

```bash
docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com \
             couchdb0 couchdb1 cli
```

### 2. Start Redis (if not running as a service)

```bash
redis-cli ping || sudo systemctl start redis-server
```

### 3. Start Backend

Must be launched from a shell with `peer` on `PATH`.

```bash
which peer   # should print a path

cd ~/Documents/project/backend
uv run uvicorn main:app --port 8000 --reload
```

Wait for `Application startup complete.`

### 4. Start Frontend

```bash
cd ~/Documents/project/frontend-vite
npm install          # first time only
npm run dev
```

Open `http://localhost:5173`.

---

## API Reference

### Stage 1 — Upload & Validate

```http
POST /api/v2/documents/validate
Content-Type: multipart/form-data

files: <binary>[]   # 1–10 images, JPEG/PNG/WebP, ≤15 MB each
```

**Response:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "expires_at": 1790394084.97,
  "blocked": false,
  "files": [
    {
      "index": 0,
      "filename": "passport.jpg",
      "quality": { "decision": "enhance", "score": 72.5, "reasons": ["tilted 12°"] },
      "classification": { "doc_type": "passport", "confidence": 0.968 },
      "enhanced": true,
      "preview_url": "/api/v2/documents/preview/sess_.../0",
      "blocked": false
    }
  ]
}
```

### Stage 2 — OCR + Validation

```http
POST /api/v2/documents/details
Content-Type: application/json

{ "session_id": "sess_a1b2c3d4e5f6" }
```

**Response:**
```json
{
  "session_id": "sess_...",
  "documents": [
    {
      "index": 0,
      "doc_type": "passport",
      "fields": { "name": "...", "passport_number": "...", "date_of_birth": "..." },
      "mrz": { "raw": ["P<IND..."] },
      "validation": { "valid": true, "errors": [], "warnings": [] },
      "ocr_failed": false
    }
  ]
}
```

### Stage 3 — Start Liveness

```http
POST /api/v2/screening/start-liveness
Content-Type: application/json

{ "session_id": "sess_...", "doc_index": 0 }
```

**Response:** `{ "liveness_session_id": "...", "blink_target": 2 }`

### Liveness loop (existing endpoints)

```http
POST /liveness/session/{id}/frame                       # push a webcam frame
POST /liveness/session/{id}/complete-blink-challenge
POST /liveness/session/{id}/anti-spoof
POST /liveness/session/{id}/face-match
POST /liveness/session/{id}/verify                      # returns JWT on success
GET  /liveness/session/{id}/status                      # poll checklist
```

### Finalize

```http
POST /api/v2/screening/finalize
Content-Type: application/json

{ "screening_session_id": "sess_...", "liveness_session_id": "..." }
```

**Response:**
```json
{
  "screening_session_id": "sess_...",
  "liveness_session_id": "...",
  "stopped_early": false,
  "liveness": {
    "blink_count": 2, "blink_target": 2,
    "anti_spoof": { "passed": true, "score": 0.99 },
    "face_match": { "passed": true, "distance": 0.48 },
    "state": "verified"
  },
  "tampering": [{ "index": 0, "tampering_score": 8.2, "is_tampered": false }],
  "validation_summary": { "expired": false, "errors": [] },
  "risk_assessment": { "score": 22.5, "decision": "APPROVE", "reasons": [] },
  "blockchain": { "recorded": true, "screening_id": "d44f0599..." }
}
```

### Screening History

```http
GET /api/v2/history?checkpoint=JFK_01&limit=50
GET /api/v2/history/{screening_id}
GET /api/v2/screening/{screening_session_id}/state
```

### Legacy (deprecated, still works)

```http
POST /api/v2/screen    # single-shot: document + live_photo
```

---

## Blockchain Setup

The system writes to a single channel `screening-channel` running **chaincode `screening` v1.0** with CouchDB as the state store and a private data collection for PII.

### Version Requirements

| Component | Version |
|---|---|
| Docker | 24.0.9 (Docker 29 breaks Fabric's chaincode builder) |
| docker-compose | 2.24.5 |
| Fabric binaries | 2.5.0 |
| fabric-samples | v2.4.9 |
| Go | 1.20.14 |
| Chaincode SDK | `fabric-chaincode-go` (no `/v2`) |

### Common pitfalls

| Don't | Why |
|---|---|
| `./network.sh up ...` **without** `-s couchdb` | Rich queries fail: `ExecuteQuery not supported for leveldb` |
| Pass `-ca` to `network.sh up` | Spins up unused CA containers, drops `-s couchdb` silently |
| Point `-ccp` at `../asset-transfer-basic/...` | Uses demo chaincode, not the screening chaincode |
| Forget `-cccg .../collections_config.json` | PII writes fail: `collection ... could not be found` |
| Run `network.sh down` casually | Wipes every ledger record — no recovery |

See [`docker.md`](docker.md) for the full reproducible setup.

### Daily operations

```bash
# Restart after reboot (fast — no state loss)
docker start orderer.example.com peer0.org1.example.com peer0.org2.example.com \
             couchdb0 couchdb1 cli

# Verify chaincode is still live
cd ~/Documents/project/fabric-samples/test-network
export PATH="$HOME/Documents/project/fabric-samples/bin:$PATH"
export FABRIC_CFG_PATH="$HOME/Documents/project/fabric-samples/config"
source ./scripts/envVar.sh && setGlobals 1
peer lifecycle chaincode querycommitted --channelID screening-channel --name screening

# Query the ledger from CLI
peer chaincode query -C screening-channel -n screening \
  -c '{"Args":["QueryScreeningsByCheckpoint","JFK_01"]}'
```

---

## Project Structure

```
project/
├── backend/
│   ├── main.py                          # FastAPI app + lifespan
│   ├── app/
│   │   ├── routers/
│   │   │   ├── documents.py             # Stages 1 + 2
│   │   │   ├── liveness.py              # Frame loop + PAD + face match
│   │   │   ├── screening_finalize.py    # start-liveness + finalize + state
│   │   │   └── screening_history.py     # Ledger read-throughs
│   │   ├── core/
│   │   │   ├── redis.py                 # Wrapped Redis client
│   │   │   ├── session.py               # Liveness session store
│   │   │   └── session_store.py         # Screening session store
│   │   └── schemas/
│   │       └── session.py               # Session Pydantic models
│   ├── services/
│   │   ├── pipeline.py                  # DocumentPipeline class
│   │   ├── ocr_service.py
│   │   ├── tampering_service.py
│   │   ├── face_service.py
│   │   ├── image_quality_service.py
│   │   ├── enhancement_service.py
│   │   ├── anti_spoof.py                # MiniFASNetV2 + heuristics
│   │   └── screen_detector.py           # Flicker/moiré replay check
│   ├── risk_engine/
│   │   └── scorer.py
│   ├── blockchain/
│   │   └── client.py                    # `peer chaincode invoke` wrapper
│   └── models/
│       ├── doc_classifier.pt
│       ├── anti_spoof.onnx
│       └── insightface/
│
├── frontend-vite/
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js                   # /api + /liveness proxy → :8000
│   ├── public/favicon.svg
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── api/client.js
│       └── components/
│           ├── Navbar.jsx
│           ├── Hero.jsx
│           ├── Sections.jsx
│           ├── Footer.jsx
│           ├── ScreeningHistory.jsx
│           ├── ui/index.jsx
│           └── wizard/
│               ├── Wizard.jsx
│               ├── StepTabs.jsx
│               ├── Step1Upload.jsx
│               ├── Step2Liveness.jsx
│               └── Step3Results.jsx
│
├── fabric-samples/
│   ├── test-network/                    # Fabric network orchestration
│   └── screening-chaincode-go/
│       ├── screening.go                 # Chaincode
│       ├── go.mod
│       └── collections_config.json      # PDC definition
│
├── enhancers/
│   ├── AI_enhance/                      # Zero-DCE
│   ├── Real-ESRGAN/                     # Super-resolution (warm on :8766)
│   └── Document-Image-Dewarping/        # Perspective correction (warm on :8765)
│
├── docker.md                            # Fabric setup, reproducible
└── readme.md
```

---

## Configuration

### Backend thresholds

| File | Constant | Default | Meaning |
|---|---|---|---|
| `risk_engine/scorer.py` | `APPROVE_THRESHOLD` | 30 | score < 30 → APPROVE |
| `risk_engine/scorer.py` | `DENY_THRESHOLD` | 70 | score > 70 → DENY |
| `services/face_service.py` | `FACE_THRESHOLD` | 0.55 | cosine similarity floor |
| `services/anti_spoof.py` | `predict()` | 0.65 | MiniFASNetV2 live-class threshold |

### Environment variables

```bash
export FABRIC_CFG_PATH="$HOME/Documents/project/fabric-samples/config"
export PATH="$HOME/Documents/project/fabric-samples/bin:$PATH"
export DEBUG_OCR=true                # optional — include raw OCR lines in response
export CUDA_VISIBLE_DEVICES=0        # optional — pin to a specific GPU
```

The backend also reads `REDIS_URL` from `backend/app/config.py`.

---

## Known Limitations

**Anti-spoof (PAD)**
`MiniFASNetV2` was trained on pre-2018 datasets (CASIA-FASD, Replay-Attack). It catches printed photos and low-resolution screen replays, but **misses modern OLED/high-DPI video replays** when the webcam sees the screen from an angle. Mitigations:
- Blink challenge requires genuine eye movement
- Face match enforces biometric identity
- `services/screen_detector.py` adds a flicker/moiré heuristic (can be strengthened)

**Blockchain durability**
The `network.sh down` command deletes all Docker volumes — **every ledger record is destroyed**. There is no automated backup. Treat the current setup as a development/demo ledger, not production storage.

**No authentication**
The FastAPI backend is open (no API keys, no rate limits). Fine for local dev; requires an API gateway in production.

**Session cleanup**
Screening sessions live 30 minutes (Redis TTL) and are swept from disk by `screening_session_store.sweep_stale()`. Liveness sessions share the same TTL.

---

## Roadmap

- [ ] Auto-refresh Screening History after finalize
- [ ] PDF audit-certificate export
- [ ] Stronger PAD model (AENet / DeepPixBiS)
- [ ] Docker Compose for the app tier (backend + frontend + Redis)
- [ ] nginx reverse proxy with TLS for single-origin deployment
- [ ] Authentication + rate limiting
- [ ] Persistent ledger volumes that survive `network.sh down`

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

Built on top of **FastAPI**, **React 19**, **Vite**, **Tailwind**, **PaddleOCR**, **TrOCR**, **InsightFace**, **PyTorch**, and **Hyperledger Fabric**.

Tampering detection training data: **CASIA v2**.