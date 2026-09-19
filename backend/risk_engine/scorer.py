class RiskScorer:
    """Weighted risk scoring with hard override for unreadable OCR."""

    WEIGHTS = {
        "tampering":  0.35,
        "face":       0.30,
        "validation": 0.20,
        "expiry":     0.15,
    }

    APPROVE_THRESHOLD = 30
    DENY_THRESHOLD = 70

    FACE_DISTANCE_SCALE = 1.0  # tune to your embedding distance range

    def calculate(
        self,
        tampering_score: float,
        face_distance: float,
        validation_errors: list,
        is_expired: bool,
        ocr_failed: bool = False,
    ) -> dict:
        reasons = []

        # Tampering: 0–100 → 0–1
        t_norm = max(0.0, min(1.0, tampering_score / 100.0))

        # Face: distance 0 = identical, larger = worse.
        f_norm = max(0.0, min(1.0, face_distance / self.FACE_DISTANCE_SCALE))

        # Validation: any error → full weight
        v_norm = 1.0 if validation_errors else 0.0

        # Expiry
        e_norm = 1.0 if is_expired else 0.0

        total = (
            self.WEIGHTS["tampering"]  * t_norm +
            self.WEIGHTS["face"]       * f_norm +
            self.WEIGHTS["validation"] * v_norm +
            self.WEIGHTS["expiry"]     * e_norm
        ) * 100.0

        if t_norm > 0.45:
            reasons.append(f"Tampering signals elevated ({tampering_score:.1f})")
        if f_norm > 0.55:
            reasons.append(f"Face similarity weak (distance={face_distance:.3f})")
        if validation_errors:
            reasons.append(f"{len(validation_errors)} validation error(s)")
        if is_expired:
            reasons.append("Document expired")

        if ocr_failed:
            total = max(total, 55.0)
            reasons.append("OCR unreadable")

        total = round(min(total, 100.0), 2)

        if total < self.APPROVE_THRESHOLD:
            decision = "APPROVE"
        elif total <= self.DENY_THRESHOLD:
            decision = "SECONDARY_INSPECTION"
        else:
            decision = "DENY"

        return {
            "score": total,
            "decision": decision,
            "reasons": reasons,
        }