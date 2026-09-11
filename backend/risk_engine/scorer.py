class RiskScorer:
    def __init__(self):
        self.weights = {
            "tampering": 0.35,
            "face_mismatch": 0.30,
            "validation_fail": 0.20,
            "expiry_risk": 0.15,
        }
        self.classification_threshold = 0.55
        self.DENY_FLOOR = 70.0
        self.SECONDARY_FLOOR = 40.0

    def calculate(
        self,
        tampering_score,
        face_distance,
        validation_errors,
        is_expired,
        *,
        document_type: str | None = None,
        classification_confidence: float | None = None,
        validation_source: str | None = None,
        has_identity_fields: bool | None = None,
    ):
        # Bug C defensive scaling: if tampering_service returns a 0-1
        # fraction, scale to 0-100 so the weight contributes correctly.
        # Remove once tampering_service.py is patched at the source.
        if 0 < tampering_score <= 1.0:
            tampering_risk = tampering_score * 100.0
        else:
            tampering_risk = min(float(tampering_score), 100.0)

        face_risk = (
            (face_distance / 0.6) * 100
            if face_distance and face_distance < 0.6
            else (100 if face_distance else 0)
        )
        validation_risk = min(len(validation_errors) * 25, 100)
        expiry_risk = 100 if is_expired else 0

        scores = {
            "tampering": round(tampering_risk, 2),
            "face_mismatch": round(face_risk, 2),
            "validation_fail": round(validation_risk, 2),
            "expiry_risk": round(expiry_risk, 2),
        }

        total = sum(scores[k] * self.weights[k] for k in self.weights)

        if total < 30:
            decision = "APPROVE"
        elif total < 70:
            decision = "SECONDARY_INSPECTION"
        else:
            decision = "DENY"

        # Bug G: unidentifiable document override
        unidentifiable = (
            document_type == "unknown"
            or (
                classification_confidence is not None
                and classification_confidence < self.classification_threshold
            )
        )

        # Bug H: no identity fields is its own escalation
        no_identity = (
            has_identity_fields is False
            or validation_source == "none"
        )

        override_reason = None

        if unidentifiable and no_identity:
            decision = "DENY"
            total = max(total, self.DENY_FLOOR)
            override_reason = (
                f"unidentifiable document: type={document_type!r} "
                f"@ conf={classification_confidence}, no extractable identity fields"
            )
        elif unidentifiable:
            if decision == "APPROVE":
                decision = "SECONDARY_INSPECTION"
            total = max(total, self.SECONDARY_FLOOR)
            override_reason = (
                f"low-confidence classification: type={document_type!r} "
                f"@ conf={classification_confidence}"
            )
        elif no_identity:
            if decision == "APPROVE":
                decision = "SECONDARY_INSPECTION"
            total = max(total, self.SECONDARY_FLOOR)
            override_reason = "no extractable identity fields"

        return {
            "total_score": round(total, 2),
            "component_scores": scores,
            "decision": decision,
            "confidence": "HIGH" if total < 20 or total > 80 else "MEDIUM",
            "override_reason": override_reason,
        }