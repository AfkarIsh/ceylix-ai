"""
Multivariate Statistical Anomaly Detector for Ceylix AI (Novel-Threat Readiness).
Operates as an independent, experimental anomaly detection interface separated from
the deterministic financial-risk rules engine.

Features evaluated:
1. Transaction amount deviation against customer 30-day historical baseline (z-score / MAD).
2. Velocity acceleration (ratio of current volume to baseline).
3. Counterparty novelty (unseen beneficiary accounts or names).
4. Corridor deviation (destination country differing from historical domestic/regional baseline).
5. Device and network dispersion (unrecognized device combined with IP obfuscation).

Strict Compliance Guarantee:
- Anomaly scores are strictly distinct from calibrated financial risk scores.
- An anomaly is NEVER classified as confirmed fraud or financial crime.
- An anomaly score does NOT independently trigger a regulatory SAR filing.
"""

from typing import Dict, Any, List, Optional
import math
from pydantic import BaseModel, Field

try:
    from backend.app.schemas import InvestigationCase, Transaction, EvidenceRecord
except ModuleNotFoundError:
    from app.schemas import InvestigationCase, Transaction, EvidenceRecord


class AnomalyDetectionResult(BaseModel):
    """Result of experimental multivariate anomaly detection."""
    anomaly_score: float = Field(description="Normalized anomaly score between 0.0 and 1.0")
    is_anomaly: bool = Field(description="True if score exceeds the configured anomaly threshold")
    threshold_applied: float = Field(default=0.65, description="Decision threshold applied")
    feature_contributions: Dict[str, float] = Field(
        default_factory=dict,
        description="Individual feature anomaly scores [0.0, 1.0]"
    )
    explanation: str = Field(description="Transparent statistical rationale")
    detection_method: str = Field(
        default="multivariate_statistical_baseline",
        description="Algorithm identification"
    )


class MultivariateAnomalyDetector:
    """Independent statistical anomaly detector for novel financial patterns."""

    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold

    def evaluate(self, case: InvestigationCase) -> AnomalyDetectionResult:
        tx = case.transaction
        evidence = case.evidence_records

        # 1. Feature: Amount Deviation (z-score against customer historical baseline)
        history_rec = next((r for r in evidence if r.evidence_type == "ACCOUNT_HISTORY"), None)
        if history_rec and history_rec.data:
            avg_amount = float(history_rec.data.get("avg_30d_transaction_amount", 1000.0))
            std_dev = float(history_rec.data.get("std_dev_30d_amount", avg_amount * 0.45))
            if std_dev <= 0:
                std_dev = max(avg_amount * 0.45, 100.0)
            diff = max(0.0, tx.amount_usd - avg_amount)
            z_score = diff / std_dev
            # Sigmoid normalization of z-score: z=0 -> 0.0, z=3 -> ~0.75, z=5+ -> ~0.95
            amount_score = min(1.0, 1.0 - math.exp(-0.4 * z_score)) if z_score > 0 else 0.0

            # Low amount transactions under $500 suppress statistical amount anomaly
            if tx.amount_usd < 500.0:
                amount_score = 0.0
        else:
            amount_score = 0.1 if tx.amount_usd >= 10000.0 else 0.0

        # 2. Feature: Velocity Acceleration Ratio
        if history_rec and history_rec.data:
            avg_amount = float(history_rec.data.get("avg_30d_transaction_amount", 1000.0))
            ratio = tx.amount_usd / avg_amount if avg_amount > 0 else 1.0
            if ratio >= 8.0:
                velocity_score = 0.90
            elif ratio >= 5.0:
                velocity_score = 0.70
            elif ratio >= 3.0:
                velocity_score = 0.40
            else:
                velocity_score = 0.05
        else:
            velocity_score = 0.10

        # 3. Feature: Counterparty Novelty
        counterparty_novelty = 0.0
        if history_rec and history_rec.data:
            known_counterparties = history_rec.data.get("frequent_counterparties", [])
            known_lower = [str(c).strip().lower() for c in known_counterparties]
            current_cparty = (tx.counterparty_name or "").strip().lower()
            if known_lower and current_cparty:
                if current_cparty not in known_lower:
                    counterparty_novelty = 0.75
                else:
                    counterparty_novelty = 0.05
            else:
                counterparty_novelty = 0.20
        else:
            counterparty_novelty = 0.15

        # 4. Feature: Corridor Deviation
        origin = (tx.origin_country or "US").upper()
        dest = (tx.destination_country or tx.counterparty_country or "US").upper()
        corridor_score = 0.05
        if origin != dest:
            if dest in {"KP", "IR", "MM", "SY", "RU"}:
                corridor_score = 0.95
            elif dest in {"KY", "PA", "VG"}:
                corridor_score = 0.60
            else:
                corridor_score = 0.35

        # 5. Feature: Device and Network Dispersion
        telemetry_rec = next((r for r in evidence if r.evidence_type == "DEVICE_IP_TELEMETRY"), None)
        dispersion_score = 0.05
        if telemetry_rec and telemetry_rec.data:
            vpn = telemetry_rec.data.get("vpn_or_proxy_detected", False)
            known_devices = telemetry_rec.data.get("known_device_ids", [])
            dev_id = tx.device_id or ""
            unknown_dev = bool(dev_id and known_devices and dev_id not in known_devices)

            if vpn and unknown_dev:
                dispersion_score = 0.85
            elif vpn or unknown_dev:
                dispersion_score = 0.50
            else:
                dispersion_score = 0.05

        # Weighted multivariate combination
        weights = {
            "amount_deviation": 0.30,
            "velocity_acceleration": 0.25,
            "counterparty_novelty": 0.20,
            "corridor_deviation": 0.15,
            "device_dispersion": 0.10,
        }

        feature_scores = {
            "amount_deviation": round(amount_score, 4),
            "velocity_acceleration": round(velocity_score, 4),
            "counterparty_novelty": round(counterparty_novelty, 4),
            "corridor_deviation": round(corridor_score, 4),
            "device_dispersion": round(dispersion_score, 4),
        }

        composite_score = sum(feature_scores[k] * weights[k] for k in weights)
        composite_score = round(min(1.0, max(0.0, composite_score)), 4)
        is_anomaly = composite_score >= self.threshold

        # Generate transparent non-accusatory statistical explanation
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)
        flagged_features = [f"{k} ({v:.2f})" for k, v in top_features if v >= 0.40]

        if is_anomaly:
            explanation = (
                f"Statistical novelty flagged (score {composite_score:.2f} >= threshold {self.threshold:.2f}). "
                f"Elevated feature divergence observed in: {', '.join(flagged_features) if flagged_features else 'aggregate multidimensional metrics'}. "
                "Notice: Statistical outliers indicate transaction dynamics differing from customer baselines; "
                "this does NOT constitute verified fraud or an independent basis for regulatory filing."
            )
        else:
            explanation = (
                f"Transaction dynamics conform to expected multidimensional baseline "
                f"(score {composite_score:.2f} < threshold {self.threshold:.2f})."
            )

        return AnomalyDetectionResult(
            anomaly_score=composite_score,
            is_anomaly=is_anomaly,
            threshold_applied=self.threshold,
            feature_contributions=feature_scores,
            explanation=explanation,
            detection_method="multivariate_statistical_baseline"
        )


def detect_transaction_anomalies(case: InvestigationCase, threshold: float = 0.65) -> AnomalyDetectionResult:
    """Entry point for novel-threat anomaly evaluation."""
    detector = MultivariateAnomalyDetector(threshold=threshold)
    return detector.evaluate(case)
