# AI-Based Document Screening System – Improvements & Blockchain Integration

## Current System Assessment

Your implementation is **production-grade** with strong fundamentals:
- ✅ Multi-signal tampering detection (5-layer fusion)
- ✅ Dual-engine OCR with fallback logic
- ✅ Graceful degradation when ML models fail
- ✅ Explainable risk scoring with human review escalation
- ✅ Real-time face verification with embeddings

**Gap**: The system lacks **immutability**, **auditability**, and **inter-authority coordination** – all critical for border security.

---

## Part 1: Technical Improvements (Non-Blockchain)

### 1. **Enhanced Biometric Matching**

**Current**: Single cosine similarity between embeddings

**Improvement**: Multi-modal biometric fusion

```python
class EnhancedBiometricService:
    def verify(self, doc_image_bytes, live_photo_bytes):
        """
        Multi-modal verification combining face, iris, fingerprint signals
        """
        # 1. Face embedding (ArcFace) – 512D
        face_sim = self.face_verify.verify(doc_image_bytes, live_photo_bytes)
        
        # 2. Iris matching (if available) – VGG-based iris encoder
        iris_sim = self.iris_matcher.match(doc_image_bytes, live_photo_bytes)
        
        # 3. Liveness detection (prevents photo attacks)
        liveness = self.liveness_detector.detect(live_photo_bytes)
        
        # 4. Age/gender consistency
        age_gender_match = self.age_gender_verifier.verify(
            doc_face_img, live_face_img
        )
        
        # Weighted fusion
        biometric_score = (
            0.50 * face_sim +
            0.20 * iris_sim +
            0.15 * liveness +
            0.15 * age_gender_match
        )
        
        return {
            "verified": biometric_score > 0.75,
            "score": round(biometric_score, 3),
            "face": face_sim,
            "iris": iris_sim,
            "liveness": liveness,
            "age_gender_match": age_gender_match,
            "confidence": "HIGH" if biometric_score > 0.85 else "MEDIUM"
        }
```

**Why**: 
- Face-only can be spoofed with high-quality masks/photos
- Multi-modal makes systematic bypass exponentially harder
- Liveness detection prevents presentation attacks

---

### 2. **Document Type-Specific Heuristics**

**Current**: Generic tampering detection across all documents

**Improvement**: Specialized detectors per document type

```python
class DocumentSpecificTamperingAnalyzer:
    """
    Different document types have unique tampering patterns
    """
    
    PATTERNS = {
        "passport": {
            "mrz_zone_position": [(height * 0.88, height)],  # Bottom 12% fixed
            "biometric_chip_location": [(0, 0, width * 0.3, height * 0.6)],
            "security_features": ["hologram", "watermark", "microprint"],
            "text_regions": {
                "name": (height * 0.15, height * 0.35),
                "dob": (height * 0.40, height * 0.50),
                "expiry": (height * 0.50, height * 0.60)
            }
        },
        "visa": {
            "stamp_regions": [(width * 0.5, height * 0.5, width, height)],
            "text_regions": {
                "visa_number": (height * 0.10, height * 0.20),
                "issue_date": (height * 0.30, height * 0.40),
                "expiry_date": (height * 0.40, height * 0.50)
            },
            "ink_colors": ["blue", "red", "black"],  # Official visa inks
        },
        "national_id": {
            "chip_position": [(width * 0.7, height * 0.1, width, height * 0.4)],
            "security_features": ["hologram", "laser_engraving"],
        }
    }
    
    def analyze(self, image_path: str, doc_type: str) -> dict:
        """Document-type aware tampering analysis"""
        pattern = self.PATTERNS.get(doc_type, {})
        
        # 1. Region-based analysis
        # Only analyze regions that should contain text/images
        suspicious_regions = self._analyze_regions(image_path, pattern)
        
        # 2. Security feature detection
        # Check for presence of hologram, microprint, etc.
        security_features = self._detect_security_features(
            image_path, 
            pattern.get("security_features", [])
        )
        
        # 3. Ink color verification
        # Ensure text colors match official document specifications
        ink_compliance = self._verify_ink_colors(
            image_path,
            pattern.get("ink_colors", [])
        )
        
        # 4. Chip/microchip validation
        # For docs with embedded chips, verify presence and authenticity
        chip_validation = self._validate_biometric_chip(
            image_path,
            pattern.get("biometric_chip_location", [])
        )
        
        return {
            "suspicious_regions": suspicious_regions,
            "missing_security_features": security_features,
            "ink_compliance": ink_compliance,
            "chip_validation": chip_validation,
            "doc_type_specific_score": self._aggregate_scores(
                suspicious_regions, security_features, ink_compliance, chip_validation
            )
        }
```

**Why**:
- Passport MRZ zone is always in bottom 12% – anomalies are red flags
- Visas have specific ink colors (official regulations)
- National IDs often have security holograms
- Type-specific patterns catch nuanced tampering

---

### 3. **Real-Time Fraud Alert System**

**Current**: Per-request screening decision

**Improvement**: Continuous threat intelligence loop

```python
class FraudIntelligenceEngine:
    """
    Aggregates screening results to detect patterns and alert authorities
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.alert_threshold = 0.85  # risk score
    
    def ingest_screening(self, screening_result: dict):
        """Process completed screening, check for patterns"""
        
        screening_id = screening_result["screening_id"]
        risk_score = screening_result["risk_assessment"]["score"]
        passport_num = screening_result["ocr_data"].get("fields", {}).get("passport_number")
        face_embedding = screening_result["biometrics"]["embedding"]
        
        # 1. Alert on high-risk individual
        if risk_score > self.alert_threshold:
            self._create_alert(
                type="HIGH_RISK_INDIVIDUAL",
                screening_id=screening_id,
                reason=screening_result["risk_assessment"]["reasons"]
            )
        
        # 2. Detect identity reuse (same passport, different faces)
        past_screenings = self.db.query(
            "SELECT * FROM screenings WHERE passport_number = %s",
            (passport_num,)
        )
        
        for past in past_screenings:
            past_embedding = past["face_embedding"]
            similarity = np.dot(face_embedding, past_embedding)
            
            if past["face_embedding"] is not None and similarity < 0.7:
                self._create_alert(
                    type="IDENTITY_REUSE",
                    screening_id=screening_id,
                    duplicate_of=past["screening_id"],
                    reason=f"Same passport, different face (sim={similarity:.2f})"
                )
        
        # 3. Detect forged document patterns
        # If multiple people with same passport in short time
        recent_count = self.db.query(
            "SELECT COUNT(*) FROM screenings WHERE passport_number = %s AND timestamp > NOW() - INTERVAL 7 DAY",
            (passport_num,)
        )[0][0]
        
        if recent_count > 3:
            self._create_alert(
                type="POTENTIAL_DOCUMENT_FORGERY",
                screening_id=screening_id,
                reason=f"Passport used {recent_count} times in 7 days"
            )
        
        # 4. Detect geo-temporal anomalies
        # Crossing two borders in impossible time window
        last_crossing = self.db.query(
            "SELECT location, timestamp FROM screenings WHERE passport_number = %s ORDER BY timestamp DESC LIMIT 1",
            (passport_num,)
        )
        
        if last_crossing:
            last_loc, last_time = last_crossing[0]
            time_diff = (datetime.now() - last_time).total_seconds() / 3600  # hours
            distance = self._geographic_distance(last_loc, screening_result["checkpoint_location"])
            
            # Impossible travel: >900 km/h sustained speed
            if distance / time_diff > 900:
                self._create_alert(
                    type="IMPOSSIBLE_TRAVEL",
                    screening_id=screening_id,
                    from_location=last_loc,
                    to_location=screening_result["checkpoint_location"],
                    time_hours=time_diff,
                    distance_km=distance
                )
        
        # 5. Detect common forgery patterns (ML-based clustering)
        # Flag documents that visually cluster with known forgeries
        tampering_vectors = self._extract_tampering_features(
            screening_result["tampering"]
        )
        
        nearest_frauds = self.fraud_classifier.find_nearest_frauds(
            tampering_vectors, k=5
        )
        
        if len(nearest_frauds) > 0 and nearest_frauds[0]["distance"] < 0.3:
            self._create_alert(
                type="KNOWN_FORGERY_PATTERN",
                screening_id=screening_id,
                similar_frauds=[f["fraud_id"] for f in nearest_frauds],
                reason="Matches known forgery pattern"
            )
    
    def _create_alert(self, type: str, **kwargs):
        """Persist alert to database and notify authorities"""
        alert = {
            "alert_type": type,
            "created_at": datetime.now(),
            "severity": "HIGH",
            **kwargs
        }
        self.db.insert("alerts", alert)
        
        # Notify border authorities via secure channel
        self._notify_authorities(alert)
```

**Why**:
- Fraud patterns emerge from aggregated data
- Real-time detection of identity reuse before harm
- Geo-temporal checks catch human trafficking, repeat offenders
- Creates actionable intelligence for border agents

---

### 4. **Continuous Model Improvement Pipeline**

**Current**: Models are static after deployment

**Improvement**: Active learning feedback loop

```python
class ContinuousModelImprovement:
    """
    Agents at checkpoints provide feedback → models improve over time
    """
    
    def __init__(self, model_registry):
        self.registry = model_registry
        self.feedback_buffer = []
        self.retraining_threshold = 10000  # retrain after 10k feedback samples
    
    def record_feedback(self, screening_id: str, agent_feedback: dict):
        """
        Border agent reviews screening result and provides ground truth
        
        agent_feedback = {
            "decision": "APPROVED" / "DENIED" / "CORRECTED",
            "actual_tampering": True/False,
            "actual_face_match": True/False,
            "notes": str,
            "agent_id": str,
            "checkpoint_id": str
        }
        """
        
        # 1. Validate feedback quality
        if self._is_trusted_agent(agent_feedback["agent_id"]):
            confidence_weight = 1.0
        else:
            confidence_weight = 0.5  # less trusted sources
        
        feedback_record = {
            "screening_id": screening_id,
            "feedback": agent_feedback,
            "confidence_weight": confidence_weight,
            "timestamp": datetime.now()
        }
        
        self.feedback_buffer.append(feedback_record)
        
        # 2. Periodically retrain models
        if len(self.feedback_buffer) >= self.retraining_threshold:
            self._trigger_retraining()
    
    def _trigger_retraining(self):
        """
        Retrain tampering detection, face verification, risk scorer
        with human-validated ground truth
        """
        
        # 1. Prepare dataset from feedback
        dataset = self._prepare_training_dataset(self.feedback_buffer)
        
        # 2. Validate dataset quality
        validation_metrics = self._validate_dataset(dataset)
        if validation_metrics["agreement_ratio"] < 0.85:
            print("Low inter-rater agreement; skipping retraining")
            return
        
        # 3. Retrain tampering detection model
        old_tampernet = self.registry.get("tampernet_v1")
        new_tampernet = self._retrain_tampernet(
            dataset["tampering_cases"],
            base_model=old_tampernet
        )
        
        # 4. A/B test new model
        # Split 1% of traffic to new model, compare metrics
        self.registry.register(
            "tampernet_v2",
            new_tampernet,
            enabled=False,
            ab_test_percentage=0.01
        )
        
        # 5. After 1 week of A/B testing, evaluate
        ab_test_results = self._evaluate_ab_test("tampernet_v2")
        
        if ab_test_results["accuracy_improvement"] > 0.02:
            # New model is better, promote to production
            self.registry.promote("tampernet_v2", to_production=True)
            self.registry.deprecate("tampernet_v1")
        
        # 6. Clear feedback buffer
        self.feedback_buffer = []
    
    def _prepare_training_dataset(self, feedback_buffer):
        """Convert agent feedback into training data"""
        return {
            "tampering_cases": [...],
            "face_verification_cases": [...],
            "validation_cases": [...]
        }
```

**Why**:
- Models trained on static data become stale
- Real-world distribution shift requires continuous adaptation
- Human feedback validates AI decisions
- A/B testing ensures new models don't regress

---

### 5. **Advanced Liveness & Presentation Attack Detection**

**Current**: No liveness detection (static photo attack vulnerability)

**Improvement**: Multi-modal liveness detection

```python
class LivenessDetector:
    """
    Prevents photo attacks, video replays, deepfakes
    """
    
    def __init__(self):
        self.challenge_engine = ChallengeEngine()
        self.deepfake_detector = DeepfakeDetectorModel()
        self.rppg_analyzer = rPPGAnalyzer()  # remote photoplethysmography
    
    def verify_liveness(self, live_video_frames: list, document_face_bytes: bytes) -> dict:
        """
        Multi-signal liveness verification during live photo capture
        """
        
        # 1. Challenge-response (most reliable)
        # Ask user to blink, turn head, smile
        challenges = self.challenge_engine.generate_random()
        # (UI guides user through challenges, returns video)
        
        blink_detected = self._detect_blink(live_video_frames)
        head_rotation = self._detect_head_rotation(live_video_frames)
        smile_detected = self._detect_smile(live_video_frames)
        
        challenge_score = (blink_detected + head_rotation + smile_detected) / 3.0
        
        # 2. Remote Photoplethysmography (rPPG)
        # Detect subtle color changes from blood flow
        # Real person: visible pulse signal
        # Photo/video: no pulse
        rppg_signal = self.rppg_analyzer.extract_signal(live_video_frames)
        pulse_detected = self._verify_pulse_plausibility(rppg_signal)
        
        # 3. Deepfake detection
        # Modern deepfakes are hard to detect, but GAN artifacts persist
        deepfake_score = self.deepfake_detector.predict(live_video_frames)
        
        # 4. Frequency domain analysis
        # Recordings have compression artifacts in frequency space
        freq_anomalies = self._analyze_compression_artifacts(live_video_frames)
        
        # 5. Texture analysis
        # Real skin has specific texture properties (pores, micro-movements)
        texture_authenticity = self._analyze_skin_texture(live_video_frames)
        
        # Fusion
        liveness_score = (
            0.40 * challenge_score +
            0.25 * pulse_detected +
            0.15 * (1.0 - deepfake_score) +
            0.10 * texture_authenticity +
            0.10 * (1.0 - freq_anomalies)
        )
        
        return {
            "liveness_verified": liveness_score > 0.75,
            "liveness_score": round(liveness_score, 3),
            "signals": {
                "challenge_response": challenge_score,
                "pulse_detected": pulse_detected,
                "deepfake_probability": deepfake_score,
                "compression_anomalies": freq_anomalies,
                "texture_authenticity": texture_authenticity
            },
            "attack_type_detected": self._identify_attack_type(
                challenge_score, pulse_detected, deepfake_score, freq_anomalies
            )
        }
    
    def _identify_attack_type(self, challenge, pulse, deepfake, compression):
        """What type of attack (if any) was attempted?"""
        if deepfake > 0.7:
            return "DEEPFAKE"
        if compression > 0.6:
            return "VIDEO_REPLAY"
        if not pulse and challenge > 0.8:
            return "PHOTO_ATTACK"  # user did challenges but no pulse
        if challenge < 0.3:
            return "UNCOOPERATIVE_USER"
        return None  # genuine
```

**Why**:
- Face verification alone can be spoofed with photos/videos
- Liveness is defense-in-depth
- Multi-modal approach: if one signal fails, others compensate
- Deepfakes are increasingly concerning threat

---

### 6. **Distributed Screening Network**

**Current**: Monolithic backend at single checkpoint

**Improvement**: Federated learning + edge deployment

```python
class DistributedScreeningNetwork:
    """
    Deploy screening models to edge devices at each checkpoint
    Centralized coordination without centralizing data
    """
    
    def __init__(self):
        self.local_model_version = "v2.1"
        self.central_coordinator = CentralCoordinator()
        self.local_storage = LocalModelStorage()
    
    def screen_locally(self, document_bytes, live_photo_bytes):
        """
        Process screening locally without sending raw images to cloud
        - Faster (no network round trip)
        - More private (images stay local)
        - Resilient (works offline)
        """
        
        ocr_result = self.ocr_model.extract(document_bytes)
        tampering_result = self.tampering_model.analyze(document_bytes)
        face_result = self.face_model.verify(document_bytes, live_photo_bytes)
        risk_score = self.risk_scorer.calculate(tampering_result, face_result, ocr_result)
        
        return risk_score
    
    def contribute_to_federated_learning(self):
        """
        Share learnings with central coordinator WITHOUT sending raw data
        """
        
        # 1. Aggregate local statistics
        local_stats = {
            "total_screenings": self.db.count("screenings"),
            "tampering_distribution": self._get_tampering_distribution(),
            "face_match_distribution": self._get_face_match_distribution(),
            "ocr_accuracy": self._compute_ocr_accuracy(),
            "false_positive_rate": self._compute_fpr(),
            "false_negative_rate": self._compute_fnr(),
        }
        
        # 2. Train local model gradient updates (federated learning)
        local_gradients = self._compute_model_gradients_on_local_data()
        
        # 3. Send only gradients + stats (not raw data) to coordinator
        self.central_coordinator.receive_update(
            checkpoint_id=self.checkpoint_id,
            stats=local_stats,
            gradients=local_gradients,
            timestamp=datetime.now()
        )
    
    def pull_updated_models(self):
        """
        Download improved models trained on aggregated data from all checkpoints
        """
        
        # Central coordinator trained new models on federated gradients
        # from 50+ checkpoints globally
        
        latest_models = self.central_coordinator.get_latest_models(
            checkpoint_id=self.checkpoint_id
        )
        
        for model_name, model_binary, version_hash in latest_models:
            # Verify model authenticity (signed by central authority)
            if self._verify_signature(model_binary, version_hash):
                self.local_storage.update_model(model_name, model_binary)
                self.local_model_version = version_hash
            else:
                raise SecurityException("Model signature verification failed")
    
    def sync_blocklist(self):
        """
        Pull updated fraudster/suspect list from central authority
        """
        latest_blocklist = self.central_coordinator.get_blocklist()
        
        # Load into memory for fast local lookups
        self.blocklist = {
            "passport_numbers": set(latest_blocklist["passports"]),
            "flagged_faces": latest_blocklist["face_embeddings"],  # k-NN index
            "known_forgeries": latest_blocklist["document_hashes"],
            "update_timestamp": latest_blocklist["timestamp"]
        }
    
    def check_blocklist(self, passport_num: str, face_embedding: list, document_hash: str):
        """Instant local lookup"""
        
        if passport_num in self.blocklist["passport_numbers"]:
            return {
                "blocked": True,
                "reason": "Passport on global blocklist",
                "alert_level": "HIGH"
            }
        
        # k-NN search for similar known forgeries
        similar_frauds = self.blocklist["flagged_faces"].search(
            face_embedding, k=5
        )
        
        if similar_frauds[0]["distance"] < 0.2:  # very similar
            return {
                "blocked": True,
                "reason": "Face matches known fraudster",
                "alert_level": "CRITICAL"
            }
        
        return {"blocked": False}
```

**Why**:
- Latency: No network dependency
- Privacy: Images never leave checkpoint
- Resilience: Works offline, graceful degradation
- Scalability: 100s of checkpoints without bottleneck
- Federated learning: Improve global model without centralizing data

---

## Part 2: Blockchain Integration Architecture

### **Why Blockchain for Border Security?**

| Challenge | Blockchain Solution |
|-----------|-------------------|
| Forged documents | Immutable certificate of authenticity on distributed ledger |
| Travel history manipulation | Immutable record of border crossings |
| Fraudster identity reuse | Smart contract auto-flags known fraudsters across all checkpoints |
| Dispute resolution | Permanent audit trail for investigations |
| Multi-authority coordination | Decentralized consensus instead of central database |
| Document tampering | Cryptographic hash verification |

---

### **Architecture: Hyperledger Fabric + Smart Contracts**

```
┌──────────────────────────────────┐
│ Border Checkpoint A               │
│ (e.g., Airport 1)                │
│ - Local screening node            │
│ - Local database                  │
│ - Fabric peer                      │
└──────┬───────────────────────────┘
       │ Screening Result
       │ (signed)
       ↓
┌──────────────────────────────────┐
│ Hyperledger Fabric Network        │
│ - Consensus mechanism (PBFT)      │
│ - Smart contract chaincode        │
│ - Immutable ledger                │
│ - Multi-authority governance      │
└──────┬───────────────────────────┘
       │
   ┌───┴────┬───────┐
   ↓        ↓       ↓
┌─────┐  ┌──────┐ ┌──────┐
│ USA │  │ EU   │ │ APAC │
│ Gov │  │ Gov  │ │ Gov  │
└─────┘  └──────┘ └──────┘
```

---

### **Blockchain Components**

#### **1. Screening Event Recording**

```python
class BlockchainScreeningRecorder:
    """
    Record screening results to Fabric ledger
    """
    
    def __init__(self, fabric_client):
        self.client = fabric_client
        self.chaincode_name = "screening-chaincode"
    
    def record_screening(self, screening_result: dict, agent_signature: str):
        """
        Record a screening to blockchain
        
        screening_result = {
            "screening_id": "abc123",
            "passport_number": "A12345678",  # hashed before storing
            "document_type": "passport",
            "tampering_score": 12.5,
            "face_match_score": 0.92,
            "risk_score": 22.5,
            "decision": "APPROVE",
            "checkpoint_id": "JFK_01",
            "timestamp": "2026-09-22T14:30:45Z",
            "agent_id": "agent_001",
            "agent_signature": "0x123abc...",  # agent certifies result
        }
        """
        
        # 1. Cryptographic hashing
        screening_hash = self._compute_hash(screening_result)
        document_hash = self._compute_document_hash(
            screening_result["document_content"]
        )
        
        # 2. Prepare blockchain transaction
        transaction = {
            "txn_type": "SCREENING_RECORD",
            "screening_id": screening_result["screening_id"],
            "document_hash": document_hash,  # proves document authenticity
            "passport_hash": sha256(screening_result["passport_number"]),
            "risk_assessment": {
                "tampering_score": screening_result["tampering_score"],
                "face_match_score": screening_result["face_match_score"],
                "final_score": screening_result["risk_score"],
                "decision": screening_result["decision"],
                "reasoning": screening_result["risk_assessment"]["reasons"]
            },
            "checkpoint_id": screening_result["checkpoint_id"],
            "timestamp": screening_result["timestamp"],
            "agent_signature": agent_signature,  # agent takes responsibility
            "screening_hash": screening_hash,
            "checkpoint_signature": self._sign_transaction(screening_result),
        }
        
        # 3. Submit to blockchain
        response = self.client.invoke(
            channel_name="screening-channel",
            chaincode_name=self.chaincode_name,
            fcn="recordScreening",
            args=[json.dumps(transaction)]
        )
        
        return {
            "blockchain_txn_id": response["txn_id"],
            "block_number": response["block_number"],
            "verification_url": f"https://screening-ledger.example.com/verify/{response['txn_id']}"
        }
    
    def _compute_hash(self, screening_result):
        """SHA-256 hash of screening metadata"""
        data = json.dumps(
            screening_result,
            sort_keys=True,
            default=str
        )
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _sign_transaction(self, screening_result):
        """Checkpoint cryptographically signs transaction"""
        # Using checkpoint's private key
        import ecdsa
        sk = ecdsa.SigningKey.from_string(self.checkpoint_private_key)
        message = self._compute_hash(screening_result)
        signature = sk.sign(message.encode())
        return signature.hex()
```

#### **2. Smart Contract for Fraud Detection**

```solidity
// screening-chaincode.go (Hyperledger Fabric chaincode)

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type ScreeningContract struct {
	contractapi.Contract
}

// Screening record structure
type Screening struct {
	ScreeningID     string    `json:"screening_id"`
	DocumentHash    string    `json:"document_hash"`
	PassportHash    string    `json:"passport_hash"`
	RiskScore       float64   `json:"risk_score"`
	Decision        string    `json:"decision"` // APPROVE, DENY, SECONDARY_INSPECTION
	CheckpointID    string    `json:"checkpoint_id"`
	Timestamp       time.Time `json:"timestamp"`
	AgentID         string    `json:"agent_id"`
	AgentSignature  string    `json:"agent_signature"`
	CheckpointSig   string    `json:"checkpoint_signature"`
	ScreeningHash   string    `json:"screening_hash"`
}

// FraudAlert represents detected fraud pattern
type FraudAlert struct {
	AlertID        string    `json:"alert_id"`
	AlertType      string    `json:"alert_type"` // IDENTITY_REUSE, FORGERY_PATTERN, etc.
	ScreeningID    string    `json:"screening_id"`
	PassportHash   string    `json:"passport_hash"`
	SeverityLevel  string    `json:"severity"`   // LOW, MEDIUM, HIGH, CRITICAL
	Description    string    `json:"description"`
	CreatedAt      time.Time `json:"created_at"`
	ResolvedAt     time.Time `json:"resolved_at,omitempty"`
	Status         string    `json:"status"`     // ACTIVE, RESOLVED, FALSE_POSITIVE
	RelatedScreenings []string `json:"related_screenings"`
}

// RecordScreening: Main entry point
func (s *ScreeningContract) RecordScreening(ctx contractapi.TransactionContextInterface, screeningJSON string) error {
	var screening Screening
	err := json.Unmarshal([]byte(screeningJSON), &screening)
	if err != nil {
		return fmt.Errorf("failed to unmarshal screening: %v", err)
	}

	// 1. Verify signatures
	if !s.verifyAgentSignature(screening) {
		return fmt.Errorf("invalid agent signature")
	}
	if !s.verifyCheckpointSignature(screening) {
		return fmt.Errorf("invalid checkpoint signature")
	}

	// 2. Validate screening data
	if err := s.validateScreening(screening); err != nil {
		return fmt.Errorf("screening validation failed: %v", err)
	}

	// 3. Check for fraud patterns
	alerts := s.checkFraudPatterns(ctx, screening)
	
	if len(alerts) > 0 {
		// Create fraud alerts on ledger
		for _, alert := range alerts {
			alertBytes, _ := json.Marshal(alert)
			ctx.GetStub().PutState(
				"alert:"+alert.AlertID,
				alertBytes,
			)
		}
		
		// Block approval if critical alert
		for _, alert := range alerts {
			if alert.SeverityLevel == "CRITICAL" {
				return fmt.Errorf("fraud alert created: %s", alert.AlertID)
			}
		}
	}

	// 4. Store screening record
	screeningBytes, err := json.Marshal(screening)
	if err != nil {
		return fmt.Errorf("failed to marshal screening: %v", err)
	}

	err = ctx.GetStub().PutState(
		"screening:"+screening.ScreeningID,
		screeningBytes,
	)
	if err != nil {
		return fmt.Errorf("failed to store screening: %v", err)
	}

	// 5. Update indices for fast lookups
	s.indexByPassport(ctx, screening)
	s.indexByCheckpoint(ctx, screening)

	// 6. Emit event for other systems to react
	ctx.GetStub().SetEvent("ScreeningRecorded", screeningBytes)

	return nil
}

// CheckFraudPatterns: Multi-signal fraud detection
func (s *ScreeningContract) checkFraudPatterns(ctx contractapi.TransactionContextInterface, screening Screening) []FraudAlert {
	var alerts []FraudAlert

	// 1. IDENTITY REUSE: Same passport, different faces in 7 days
	alertType1 := s.checkIdentityReuse(ctx, screening)
	if alertType1 != nil {
		alerts = append(alerts, *alertType1)
	}

	// 2. DOCUMENT FORGERY: Same passport used 3+ times by different people
	alertType2 := s.checkDocumentForgery(ctx, screening)
	if alertType2 != nil {
		alerts = append(alerts, *alertType2)
	}

	// 3. IMPOSSIBLE TRAVEL: Crossing two borders in impossible time
	alertType3 := s.checkImpossibleTravel(ctx, screening)
	if alertType3 != nil {
		alerts = append(alerts, *alertType3)
	}

	// 4. KNOWN FRAUDSTER: Face in global fraud registry
	alertType4 := s.checkKnownFraudster(ctx, screening)
	if alertType4 != nil {
		alerts = append(alerts, *alertType4)
	}

	// 5. DENIED BEFORE: Same person denied at other checkpoint
	alertType5 := s.checkPriorDenial(ctx, screening)
	if alertType5 != nil {
		alerts = append(alerts, *alertType5)
	}

	return alerts
}

// CheckIdentityReuse: Query ledger for same passport in short time
func (s *ScreeningContract) checkIdentityReuse(ctx contractapi.TransactionContextInterface, current Screening) *FraudAlert {
	// Query: "SELECT * FROM ledger WHERE passport_hash = X AND timestamp > NOW - 7 days"
	
	queryString := fmt.Sprintf(`
		{
			"selector": {
				"passport_hash": "%s",
				"timestamp": {"$gt": %d}
			}
		}
	`, current.PassportHash, time.Now().AddDate(0, 0, -7).Unix())

	resultsIterator, err := ctx.GetStub().GetQueryResultsWithPagination(queryString, 100)
	if err != nil {
		return nil
	}
	defer resultsIterator.Close()

	var previousScreenings []Screening
	for resultsIterator.HasNext() {
		queryResponse, _ := resultsIterator.Next()
		var screening Screening
		json.Unmarshal(queryResponse.Value, &screening)
		previousScreenings = append(previousScreenings, screening)
	}

	// If same passport used 2+ times in 7 days = identity reuse flag
	if len(previousScreenings) >= 2 {
		return &FraudAlert{
			AlertID:       generateAlertID(),
			AlertType:     "IDENTITY_REUSE",
			ScreeningID:   current.ScreeningID,
			PassportHash:  current.PassportHash,
			SeverityLevel: "HIGH",
			Description:   fmt.Sprintf("Passport used %d times in 7 days", len(previousScreenings)+1),
			CreatedAt:     time.Now(),
			Status:        "ACTIVE",
			RelatedScreenings: getScreeningIDs(previousScreenings),
		}
	}

	return nil
}

// CheckDocumentForgery: Same document used with different faces
func (s *ScreeningContract) checkDocumentForgery(ctx contractapi.TransactionContextInterface, current Screening) *FraudAlert {
	// Query: "SELECT * FROM ledger WHERE document_hash = X"
	
	queryString := fmt.Sprintf(`
		{
			"selector": {
				"document_hash": "%s"
			}
		}
	`, current.DocumentHash)

	resultsIterator, _ := ctx.GetStub().GetQueryResultsWithPagination(queryString, 100)
	defer resultsIterator.Close()

	var previousScreenings []Screening
	for resultsIterator.HasNext() {
		queryResponse, _ := resultsIterator.Next()
		var screening Screening
		json.Unmarshal(queryResponse.Value, &screening)
		if screening.PassportHash != current.PassportHash {
			// Same document, different passport = forgery!
			previousScreenings = append(previousScreenings, screening)
		}
	}

	if len(previousScreenings) > 0 {
		return &FraudAlert{
			AlertID:       generateAlertID(),
			AlertType:     "DOCUMENT_FORGERY",
			ScreeningID:   current.ScreeningID,
			PassportHash:  current.PassportHash,
			SeverityLevel: "CRITICAL",
			Description:   fmt.Sprintf("Document used with %d different passports", len(previousScreenings)+1),
			CreatedAt:     time.Now(),
			Status:        "ACTIVE",
			RelatedScreenings: getScreeningIDs(previousScreenings),
		}
	}

	return nil
}

// CheckImpossibleTravel: Geographic/temporal impossibility
func (s *ScreeningContract) checkImpossibleTravel(ctx contractapi.TransactionContextInterface, current Screening) *FraudAlert {
	// Get last screening for this passport
	queryString := fmt.Sprintf(`
		{
			"selector": {
				"passport_hash": "%s"
			},
			"sort": [{"timestamp": "desc"}],
			"limit": 1
		}
	`, current.PassportHash)

	resultsIterator, _ := ctx.GetStub().GetQueryResultsWithPagination(queryString, 1)
	defer resultsIterator.Close()

	if !resultsIterator.HasNext() {
		return nil // First time, no prior screening
	}

	queryResponse, _ := resultsIterator.Next()
	var lastScreening Screening
	json.Unmarshal(queryResponse.Value, &lastScreening)

	// Calculate distance and time
	distance := s.geographicDistance(lastScreening.CheckpointID, current.CheckpointID)
	timeDiff := current.Timestamp.Sub(lastScreening.Timestamp)
	speedKmh := distance / timeDiff.Hours()

	// Impossible if speed > 900 km/h (commercial flight max is ~900)
	if speedKmh > 900 {
		return &FraudAlert{
			AlertID:       generateAlertID(),
			AlertType:     "IMPOSSIBLE_TRAVEL",
			ScreeningID:   current.ScreeningID,
			PassportHash:  current.PassportHash,
			SeverityLevel: "CRITICAL",
			Description:   fmt.Sprintf("Traveled %.0f km in %.1f hours (%.0f km/h)", distance, timeDiff.Hours(), speedKmh),
			CreatedAt:     time.Now(),
			Status:        "ACTIVE",
			RelatedScreenings: []string{lastScreening.ScreeningID},
		}
	}

	return nil
}

// CheckKnownFraudster: Query global fraudster registry
func (s *ScreeningContract) checkKnownFraudster(ctx contractapi.TransactionContextInterface, current Screening) *FraudAlert {
	// Query registry (could be in separate chaincode or channel)
	fraudRecord := ctx.GetStub().GetState("fraudster:" + current.PassportHash)
	if fraudRecord != nil {
		return &FraudAlert{
			AlertID:       generateAlertID(),
			AlertType:     "KNOWN_FRAUDSTER",
			ScreeningID:   current.ScreeningID,
			PassportHash:  current.PassportHash,
			SeverityLevel: "CRITICAL",
			Description:   "Passport holder is on global fraudster watchlist",
			CreatedAt:     time.Now(),
			Status:        "ACTIVE",
		}
	}
	return nil
}

// CheckPriorDenial: Was this person denied at another checkpoint?
func (s *ScreeningContract) checkPriorDenial(ctx contractapi.TransactionContextInterface, current Screening) *FraudAlert {
	queryString := fmt.Sprintf(`
		{
			"selector": {
				"passport_hash": "%s",
				"decision": "DENY"
			}
		}
	`, current.PassportHash)

	resultsIterator, _ := ctx.GetStub().GetQueryResultsWithPagination(queryString, 10)
	defer resultsIterator.Close()

	count := 0
	var priorScreenings []string
	for resultsIterator.HasNext() {
		queryResponse, _ := resultsIterator.Next()
		var screening Screening
		json.Unmarshal(queryResponse.Value, &screening)
		count++
		priorScreenings = append(priorScreenings, screening.ScreeningID)
	}

	if count > 0 {
		return &FraudAlert{
			AlertID:       generateAlertID(),
			AlertType:     "PRIOR_DENIAL",
			ScreeningID:   current.ScreeningID,
			PassportHash:  current.PassportHash,
			SeverityLevel: "HIGH",
			Description:   fmt.Sprintf("Denied %d time(s) at other checkpoints", count),
			CreatedAt:     time.Now(),
			Status:        "ACTIVE",
			RelatedScreenings: priorScreenings,
		}
	}

	return nil
}

// Helper functions
func generateAlertID() string {
	return fmt.Sprintf("alert_%d", time.Now().UnixNano())
}

func getScreeningIDs(screenings []Screening) []string {
	ids := make([]string, len(screenings))
	for i, s := range screenings {
		ids[i] = s.ScreeningID
	}
	return ids
}

// Cryptographic verification functions (stubbed)
func (s *ScreeningContract) verifyAgentSignature(screening Screening) bool {
	// Verify ECDSA signature from agent's private key
	return true
}

func (s *ScreeningContract) verifyCheckpointSignature(screening Screening) bool {
	// Verify checkpoint's signature
	return true
}

func (s *ScreeningContract) validateScreening(screening Screening) error {
	if screening.ScreeningID == "" {
		return fmt.Errorf("missing screening_id")
	}
	if screening.DocumentHash == "" {
		return fmt.Errorf("missing document_hash")
	}
	if screening.PassportHash == "" {
		return fmt.Errorf("missing passport_hash")
	}
	return nil
}

func (s *ScreeningContract) geographicDistance(checkpoint1, checkpoint2 string) float64 {
	// Look up coordinates, compute Haversine distance
	// Stubbed here
	return 5000.0 // km, example value
}
```

---

#### **3. Query Interface: Verify Screening on Public Portal**

```python
class PublicScreeningVerifier:
    """
    Citizens and authorities can verify screening authenticity
    """
    
    def verify_screening(self, screening_id: str):
        """
        Public query: "Is this screening record legitimate?"
        """
        
        # Query blockchain
        screening = self.blockchain_client.query(
            channel="screening-channel",
            chaincode="screening-chaincode",
            fcn="getScreening",
            args=[screening_id]
        )
        
        if not screening:
            return {"verified": False, "error": "Screening not found on ledger"}
        
        # 1. Verify hashes
        computed_hash = self._compute_hash(screening)
        if computed_hash != screening["screening_hash"]:
            return {"verified": False, "error": "Screening has been tampered with"}
        
        # 2. Verify signatures
        if not self._verify_agent_sig(screening):
            return {"verified": False, "error": "Invalid agent signature"}
        
        if not self._verify_checkpoint_sig(screening):
            return {"verified": False, "error": "Invalid checkpoint signature"}
        
        # 3. Check block immutability
        block_hash = self.blockchain_client.getBlockByTxnID(screening_id)
        if not self._verify_block_chain(block_hash):
            return {"verified": False, "error": "Block chain broken"}
        
        # 4. Return verifi cation details
        return {
            "verified": True,
            "screening_id": screening_id,
            "block_number": screening["block_number"],
            "timestamp": screening["timestamp"],
            "checkpoint": screening["checkpoint_id"],
            "agent": screening["agent_id"],
            "risk_score": screening["risk_score"],
            "decision": screening["decision"],
            "hash_verification": "PASSED",
            "signature_verification": "PASSED",
            "immutability_verification": "PASSED",
            "public_url": f"https://screening-explorer.gov/verify/{screening_id}"
        }
```

---

#### **4. Cross-Border Coordination**

```python
class CrossBorderCoordination:
    """
    Real-time coordination between countries without central authority
    """
    
    def __init__(self):
        self.fabric_client = FabricClient()
        self.alert_channels = {
            "usa": "screening-channel-usa",
            "eu": "screening-channel-eu",
            "apac": "screening-channel-apac",
            "cross-border": "screening-channel-global"  # interconnected
        }
    
    def escalate_alert_globally(self, fraud_alert: dict):
        """
        High-risk individual detected at one checkpoint?
        Instantly notify all other checkpoints globally
        """
        
        # 1. Record alert on local channel
        self.fabric_client.invoke(
            channel="screening-channel-usa",
            fcn="recordAlert",
            args=[json.dumps(fraud_alert)]
        )
        
        # 2. Cross-chain message: notify other regions
        message = {
            "alert_type": fraud_alert["alert_type"],
            "passport_hash": fraud_alert["passport_hash"],
            "severity": fraud_alert["severity"],
            "description": fraud_alert["description"],
            "originating_checkpoint": fraud_alert["originating_checkpoint"],
            "timestamp": fraud_alert["created_at"],
            "relay_signature": self._sign_message(fraud_alert),
        }
        
        # Send to EU channel
        self.fabric_client.invoke(
            channel="screening-channel-eu",
            fcn="receiveAlertFromOtherRegion",
            args=[json.dumps(message)]
        )
        
        # Send to APAC channel
        self.fabric_client.invoke(
            channel="screening-channel-apac",
            fcn="receiveAlertFromOtherRegion",
            args=[json.dumps(message)]
        )
        
        # 3. Update global blocklist
        self._add_to_global_blocklist(fraud_alert["passport_hash"])
    
    def _add_to_global_blocklist(self, passport_hash: str):
        """
        Add fraudster to global watchlist
        Automatically blocks at all checkpoints
        """
        
        self.fabric_client.invoke(
            channel="screening-channel-global",
            fcn="addFraudster",
            args=[
                passport_hash,
                json.dumps({
                    "alert_level": "CRITICAL",
                    "timestamp": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=365)).isoformat()
                })
            ]
        )
    
    def query_global_blocklist(self, passport_hash: str):
        """
        Check if someone is globally flagged
        """
        
        result = self.fabric_client.query(
            channel="screening-channel-global",
            fcn="getBlocklistStatus",
            args=[passport_hash]
        )
        
        if result["found"]:
            return {
                "blocked": True,
                "reason": "On global watchlist",
                "alert_level": result["alert_level"],
                "added_timestamp": result["timestamp"],
                "expires_at": result["expires_at"],
                "originating_checkpoint": result["originating_checkpoint"]
            }
        
        return {"blocked": False}
```

---

#### **5. Privacy & GDPR Compliance**

```python
class BlockchainPrivacy:
    """
    Store sensitive data privately while keeping metadata on blockchain
    """
    
    def __init__(self):
        self.private_storage = ConfidentialDataStore()  # Encrypted, access-controlled
        self.blockchain_client = FabricClient()
    
    def record_screening_privately(self, screening: dict):
        """
        GDPR-compliant: store PII separately, reference it on blockchain
        """
        
        # 1. Extract sensitive fields
        sensitive = {
            "name": screening["name"],
            "dob": screening["dob"],
            "passport_number": screening["passport_number"],
            "face_embedding": screening["face_embedding"],
        }
        
        # 2. Store in private vault with encryption + access control
        private_data_key = self.private_storage.store(
            data=sensitive,
            encryption_key=self._derive_key(screening["passport_number"]),
            access_policy={
                "authorized_roles": ["border_agent", "law_enforcement"],
                "data_retention_days": 90,
                "audit_log": True
            }
        )
        
        # 3. Store only metadata on blockchain (immutable record)
        blockchain_record = {
            "screening_id": screening["screening_id"],
            "document_hash": sha256(screening["document"]),
            "private_data_pointer": private_data_key,
            "passport_hash": sha256(screening["passport_number"]),
            "tampering_score": screening["tampering_score"],
            "risk_score": screening["risk_score"],
            "decision": screening["decision"],
            "checkpoint_id": screening["checkpoint_id"],
            "timestamp": screening["timestamp"],
            # NO: name, DOB, face embedding (stored privately)
        }
        
        # 4. Record on blockchain
        self.blockchain_client.invoke(
            channel="screening-channel",
            fcn="recordScreening",
            args=[json.dumps(blockchain_record)]
        )
        
        return {
            "stored_on_blockchain": True,
            "private_data_encrypted": True,
            "private_data_key": private_data_key,
            "retention_period_days": 90,
            "gdpr_compliant": True
        }
    
    def query_private_data(self, screening_id: str, requester_role: str):
        """
        Access to PII requires authentication + audit log
        """
        
        # 1. Verify requester has permission
        if requester_role not in ["law_enforcement", "authorized_agent"]:
            raise PermissionError(f"{requester_role} cannot access PII")
        
        # 2. Get private data pointer from blockchain
        blockchain_record = self.blockchain_client.query(
            fcn="getScreening",
            args=[screening_id]
        )
        
        # 3. Decrypt and retrieve
        sensitive_data = self.private_storage.retrieve(
            key=blockchain_record["private_data_pointer"],
            requester_id=requester_role,
            reason="border_verification"  # audit log entry
        )
        
        # 4. Log access (audit trail)
        self._log_access(
            screening_id=screening_id,
            accessed_by=requester_role,
            timestamp=datetime.now(),
            action="PII_RETRIEVED"
        )
        
        return sensitive_data
```

---

### **Blockchain Benefits Summary**

| Benefit | Implementation |
|---------|----------------|
| **Immutability** | Cryptographic hashing + consensus mechanism prevents tampering |
| **Auditability** | Every screening decision permanently recorded with timestamp, agent signature |
| **Decentralization** | No single point of failure; all checkpoints have copy of ledger |
| **Fraud Detection** | Smart contracts auto-flag identity reuse, impossible travel, known fraudsters |
| **Multi-Authority** | Countries coordinate without centralizing data; consensus-based decisions |
| **Privacy** | Sensitive data encrypted off-chain; blockchain stores only hashes + metadata |
| **Transparency** | Citizens can verify screening authenticity via public explorer |
| **Dispute Resolution** | Immutable record of who approved/denied and why; clear accountability |

---

## Part 3: Implementation Roadmap

### **Phase 1: Foundation (Months 1–3)**

- [x] OCR + Document validation (already done)
- [x] Tampering detection (already done)
- [x] Face verification (already done)
- [x] Risk scoring (already done)
- ✓ **TODO**: Add liveness detection
- ✓ **TODO**: Implement continuous model improvement loop

### **Phase 2: Intelligence & Coordination (Months 4–6)**

- ✓ **TODO**: Build fraud alert system (identity reuse, impossible travel)
- ✓ **TODO**: Deploy distributed screening network (edge devices + federated learning)
- ✓ **TODO**: Set up multi-checkpoint coordination dashboard

### **Phase 3: Blockchain Integration (Months 7–9)**

- ✓ **TODO**: Deploy Hyperledger Fabric network
- ✓ **TODO**: Write screening chaincode (smart contracts)
- ✓ **TODO**: Build blockchain recording pipeline
- ✓ **TODO**: Implement cross-border alert system
- ✓ **TODO**: Public verification portal

### **Phase 4: Scale & Harden (Months 10–12)**

- ✓ **TODO**: Deploy to 50+ checkpoints
- ✓ **TODO**: Setup GDPR/privacy compliance
- ✓ **TODO**: Conduct security audits
- ✓ **TODO**: Train border agents on system
- ✓ **TODO**: Launch public transparency reports

---

## Summary: From AI to Blockchain Trust

Your current system is **technically excellent** but lacks the **trust infrastructure** needed for government border security. Here's the full picture:

**What you have**:
- ✅ Accurate tampering detection (5-signal fusion)
- ✅ Fast face matching (sub-second)
- ✅ Explainable risk scoring

**What you need**:
- 🔵 Immutable audit trail (blockchain)
- 🔵 Real-time cross-border coordination (distributed ledger)
- 🔵 Fraud pattern detection (smart contracts)
- 🔵 Privacy compliance (encrypted PII + on-chain metadata)
- 🔵 Public verification (transparency)

**Recommended approach**:
1. Add liveness detection + continuous learning (Phase 1)
2. Implement fraud intelligence engine (Phase 2)
3. Deploy Hyperledger Fabric for immutability (Phase 3)
4. Scale to 50+ checkpoints with federated model updates (Phase 4)

This transforms your system from **"fast AI screening"** → **"trustworthy, auditable, coordinated border security infrastructure"**.
