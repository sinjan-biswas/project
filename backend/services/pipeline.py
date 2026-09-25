import os
import tempfile
import uuid
import hashlib
import time as _t
from datetime import datetime, timezone

from fastapi import HTTPException

from services.document_classifier import DocumentClassifier


class DocumentPipeline:
    """
    Full 8-layer screening pipeline extracted from main.py's original handler.
    Called by both the legacy /api/v2/screen endpoint and the batch orchestrator.
    """

    def __init__(self,
                 quality_gate,
                 enhancer,
                 ocr,
                 validator,
                 tampering,
                 face_verify,
                 scorer,
                 get_fabric,
                 qg_cache,
                 enhancer_cache_dir,
                 global_broadcast_threshold):
        self.quality_gate = quality_gate
        self.enhancer = enhancer
        self.ocr = ocr
        self.validator = validator
        self.tampering = tampering
        self.face_verify = face_verify
        self.scorer = scorer
        self.get_fabric = get_fabric
        self.qg_cache = qg_cache
        self.enhancer_cache_dir = enhancer_cache_dir
        self.global_broadcast_threshold = global_broadcast_threshold

        # Exposed for FileRoleClassifier
        try:
            self.doc_classifier = DocumentClassifier()
        except Exception as e:
            print(f"[pipeline] DocumentClassifier init failed: {e}")
            self.doc_classifier = None

    async def run_document(self, doc_bytes: bytes, filename: str, live_bytes: bytes | None = None):
        timings = {"start": _t.time()}

        def _mark(label):
            timings[label] = _t.time()
            keys = list(timings.keys())
            prev = keys[-2]
            print(f"[timing] {prev} → {label}: {timings[label] - timings[prev]:.2f}s")

        # ---- Layer 1 — Quality Gate (cached) ------------------------------
        qg_key = hashlib.sha256(doc_bytes).hexdigest()
        if qg_key in self.qg_cache:
            quality = self.qg_cache[qg_key]
            print("[timing] quality_gate: cache HIT")
        else:
            quality = self.quality_gate.assess(doc_bytes)
            self.qg_cache[qg_key] = quality
            _mark("quality_gate")

        if quality["decision"] == "reject":
            raise HTTPException(status_code=422, detail={
                "error": "image_quality_rejected",
                "quality_score": quality["score"],
                "metrics": quality["metrics"],
                "fix_instructions": quality["reasons"],
            })

        # ---- Layer 2 — Enhancement Retry ----------------------------------
        was_enhanced = False
        if quality["decision"] == "enhance":
            pre_hash = hashlib.sha256(doc_bytes).hexdigest()
            enhancer_cache_hit = os.path.exists(
                os.path.join(self.enhancer_cache_dir, pre_hash + ".pkl"))

            try:
                doc_bytes, was_enhanced = await self.enhancer.enhance(doc_bytes, quality)
                _mark("enhance")
            except Exception:
                raise HTTPException(status_code=422, detail={
                    "error": "enhancement_failed",
                    "fix_instructions": quality["reasons"],
                })

            new_hash = hashlib.sha256(doc_bytes).hexdigest()
            if enhancer_cache_hit and new_hash in self.qg_cache:
                quality = self.qg_cache[new_hash]
            else:
                quality = self.quality_gate.assess(doc_bytes)
                self.qg_cache[new_hash] = quality
                _mark("quality_recheck")

            if quality["decision"] == "reject":
                raise HTTPException(status_code=422, detail={
                    "error": "still_unreadable_after_enhancement",
                    "fix_instructions": quality["reasons"],
                })

        # ---- Layer 3 — OCR ------------------------------------------------
        try:
            ocr_data = self.ocr.extract(doc_bytes)
        except Exception as e:
            ocr_data = {"success": False, "error": f"OCR exception: {e}"}
        _mark("ocr")

        ocr_failed = not ocr_data.get("success", False)
        ocr_data["image_quality"] = quality["score"]
        ocr_data["image_enhanced"] = was_enhanced

        # ---- Layer 4 — Validation -----------------------------------------
        if ocr_failed:
            validation = {
                "valid": False,
                "errors": [f"OCR failed: {ocr_data.get('error', 'unknown')}"],
                "document_type": ocr_data.get("document_type"),
                "expiry_date": None,
            }
        else:
            validation = self.validator.validate(ocr_data)
        _mark("validation")

        # ---- Layer 5 — Tampering ------------------------------------------
        tampering_result = {"tampering_score": 0.0, "is_tampered": False, "risk_factors": []}
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(doc_bytes)
            temp_path = tmp_file.name
        try:
            tampering_result = self.tampering.analyze(
                temp_path, ocr_lines=ocr_data.get("ocr_lines", []))
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        _mark("tampering")

        # ---- Layer 6 — Face Verification ----------------------------------
        if live_bytes is not None:
            face_result = self.face_verify.verify(doc_bytes, live_bytes)
        else:
            face_result = {
                "verified": False, "distance": 1.0, "similarity": 0.0,
                "threshold": self.face_verify.threshold, "confidence": 0.0,
                "model": self.face_verify.model_name,
                "note": "No live photo provided",
            }
        _mark("face_verify")

        # ---- Layer 7 — Risk Scoring ---------------------------------------
        is_expired = any("expired" in e.lower() for e in validation.get("errors", []))
        risk = self.scorer.calculate(
            tampering_score=tampering_result.get("tampering_score", 0),
            face_distance=face_result.get("distance", 0),
            validation_errors=validation.get("errors", []),
            is_expired=is_expired,
            ocr_failed=ocr_failed,
            image_enhanced=was_enhanced,
            image_quality=quality["score"],
        )
        _mark("risk")

        if ocr_failed and risk.get("decision") == "APPROVE":
            risk["decision"] = "SECONDARY_INSPECTION"
            risk.setdefault("reasons", []).append("OCR unreadable — manual review required")

        # ---- Layer 8 — Blockchain -----------------------------------------
        screening_id = uuid.uuid4().hex[:16]
        blockchain_ok = False
        blockchain_error = None
        global_broadcast_ok = False

        try:
            fabric = self.get_fabric()
            ocr_fields = (ocr_data.get("fields") or {})
            passport_number = str(ocr_fields.get("passport_number", "unknown"))
            passport_hash = hashlib.sha256(passport_number.encode()).hexdigest()

            fabric.record_screening(
                screening={
                    "screening_id": screening_id,
                    "document_hash": hashlib.sha256(doc_bytes).hexdigest(),
                    "passport_hash": passport_hash,
                    "risk_score": float(risk.get("score", 0)),
                    "decision": str(risk.get("decision", "UNKNOWN")),
                    "checkpoint_id": "JFK_01",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_signature": "",
                },
                pii={
                    "screening_id": screening_id,
                    "name": str(ocr_fields.get("name", "")),
                    "father_name": str(ocr_fields.get("father_name", "")),
                    "passport_number": passport_number,
                    "date_of_birth": str(ocr_fields.get("date_of_birth", "")),
                },
            )
            blockchain_ok = True

            if float(risk.get("score", 0)) > self.global_broadcast_threshold:
                try:
                    fabric.broadcast_alert({
                        "screening_id": screening_id + "_global",
                        "document_hash": hashlib.sha256(doc_bytes).hexdigest(),
                        "passport_hash": passport_hash,
                        "risk_score": float(risk.get("score", 0)),
                        "decision": str(risk.get("decision", "DENY")),
                        "checkpoint_id": "JFK_01",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_signature": "",
                    })
                    global_broadcast_ok = True
                except Exception as e:
                    print(f"global broadcast failed: {e}")
        except Exception as e:
            blockchain_error = str(e)
        _mark("blockchain")

        if os.getenv("DEBUG_OCR", "false").lower() != "true":
            ocr_data = {k: v for k, v in ocr_data.items() if k != "ocr_lines"}

        total = _t.time() - timings["start"]
        print(f"[timing] ===== TOTAL: {total:.2f}s =====")

        return {
            "screening_id": screening_id,
            "document_type": ocr_data.get("document_type"),
            "ocr_data": ocr_data,
            "validation": validation,
            "tampering": tampering_result,
            "biometrics": face_result,
            "risk_assessment": risk,
            "blockchain": {
                "screening_id": screening_id,
                "recorded": blockchain_ok,
                "pii_stored_privately": blockchain_ok,
                "global_broadcast": global_broadcast_ok,
                **({"error": blockchain_error} if blockchain_error else {}),
            },
            "timestamp": datetime.now().isoformat(),
        }