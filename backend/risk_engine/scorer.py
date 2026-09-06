class RiskScorer:
    def __init__(self):
        self.weights = {
            "tampering": 0.35,
            "face_mismatch": 0.30,
            "validation_fail": 0.20,
            "expiry_risk": 0.15,
        }

    def calculate(self, tampering_score, face_distance, validation_errors, is_expired):
        tampering_risk = min(tampering_score, 100.0)
        face_risk = (face_distance / 0.6) * 100 if face_distance and face_distance < 0.6 else 100 if face_distance else 0
        validation_risk = min(len(validation_errors) * 25, 100)
        expiry_risk = 100 if is_expired else 0

        scores = {
            "tampering": tampering_risk,
            "face_mismatch": face_risk,
            "validation_fail": validation_risk,
            "expiry_risk": expiry_risk,
        }

        total = sum(scores[k] * self.weights[k] for k in self.weights)

        if total < 30:
            decision = "APPROVE"
        elif total < 70:
            decision = "SECONDARY_INSPECTION"
        else:
            decision = "DENY"

        return {
            "total_score": round(total, 2),
            "component_scores": scores,
            "decision": decision,
            "confidence": "HIGH" if total < 20 or total > 80 else "MEDIUM",
        }
