"""
Deterministic transaction risk rules for Ceylix AI.
These rules run explicitly over case data to provide transparent, inspectable risk signals.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
try:
    from backend.app.schemas import (
        Transaction,
        EvidenceRecord,
        RuleEvaluationResult,
        InvestigationCase,
    )
except ModuleNotFoundError:
    from app.schemas import (
        Transaction,
        EvidenceRecord,
        RuleEvaluationResult,
        InvestigationCase,
    )

HIGH_RISK_JURISDICTIONS = {"KP", "IR", "MM", "KY", "PA", "VG", "RU", "SY"}
LARGE_AMOUNT_THRESHOLD = 10000.0
STRUCTURING_LOWER_BOUND = 9000.0
STRUCTURING_UPPER_BOUND = 9999.99


def find_evidence_by_type(records: List[EvidenceRecord], ev_type: str) -> Optional[EvidenceRecord]:
    for rec in records:
        if rec.evidence_type == ev_type:
            return rec
    return None


def evaluate_large_amount(tx: Transaction) -> RuleEvaluationResult:
    is_large = tx.amount >= LARGE_AMOUNT_THRESHOLD
    return RuleEvaluationResult(
        rule_name="LargeAmountThresholdRule",
        rule_description=f"Flags transactions exceeding ${LARGE_AMOUNT_THRESHOLD:,.2f} USD equivalent",
        passed=not is_large,
        flagged=is_large,
        details=f"Transaction amount ${tx.amount:,.2f} {tx.currency} (Threshold: ${LARGE_AMOUNT_THRESHOLD:,.2f})",
        severity="HIGH" if is_large else "INFO",
        evidence_ids=[]
    )


def evaluate_structuring(tx: Transaction) -> RuleEvaluationResult:
    is_structuring = STRUCTURING_LOWER_BOUND <= tx.amount <= STRUCTURING_UPPER_BOUND
    return RuleEvaluationResult(
        rule_name="StructuringSmurfingRule",
        rule_description="Flags transactions just below the $10,000 CTR reporting threshold (potential structuring)",
        passed=not is_structuring,
        flagged=is_structuring,
        details=f"Amount ${tx.amount:,.2f} in range [${STRUCTURING_LOWER_BOUND:,.2f}, ${STRUCTURING_UPPER_BOUND:,.2f}]",
        severity="HIGH" if is_structuring else "INFO",
        evidence_ids=[]
    )


def evaluate_high_risk_jurisdiction(tx: Transaction) -> RuleEvaluationResult:
    is_high_risk = tx.counterparty_country.upper() in HIGH_RISK_JURISDICTIONS
    return RuleEvaluationResult(
        rule_name="HighRiskJurisdictionRule",
        rule_description="Flags counterparty beneficiaries in high-risk or secrecy jurisdictions",
        passed=not is_high_risk,
        flagged=is_high_risk,
        details=f"Counterparty country '{tx.counterparty_country}' (High-risk match: {is_high_risk})",
        severity="HIGH" if is_high_risk else "INFO",
        evidence_ids=[]
    )


def evaluate_velocity_anomaly(tx: Transaction, records: List[EvidenceRecord]) -> RuleEvaluationResult:
    history_rec = find_evidence_by_type(records, "ACCOUNT_HISTORY")
    if not history_rec:
        return RuleEvaluationResult(
            rule_name="VelocityAnomalyRule",
            rule_description="Compares transaction amount against 30-day historical average volume",
            passed=True,
            flagged=False,
            details="Account history record not available for velocity evaluation",
            severity="INFO",
            evidence_ids=[]
        )
    
    avg_amount = float(history_rec.data.get("avg_30d_transaction_amount", 1000.0))
    ratio = tx.amount / avg_amount if avg_amount > 0 else 1.0
    is_anomaly = ratio >= 5.0

    return RuleEvaluationResult(
        rule_name="VelocityAnomalyRule",
        rule_description="Compares transaction amount against 30-day historical average volume (>5x baseline)",
        passed=not is_anomaly,
        flagged=is_anomaly,
        details=f"Transaction is {ratio:.1f}x historical average (${avg_amount:,.2f})",
        severity="HIGH" if is_anomaly else "INFO",
        evidence_ids=[history_rec.evidence_id]
    )


def evaluate_device_anomaly(tx: Transaction, records: List[EvidenceRecord]) -> RuleEvaluationResult:
    telemetry_rec = find_evidence_by_type(records, "DEVICE_IP_TELEMETRY")
    if not telemetry_rec:
        return RuleEvaluationResult(
            rule_name="DeviceAnomalyRule",
            rule_description="Validates transaction device against known registered customer devices",
            passed=True,
            flagged=False,
            details="Device telemetry record not available",
            severity="INFO",
            evidence_ids=[]
        )
    
    known_devices = telemetry_rec.data.get("known_device_ids", [])
    vpn_detected = telemetry_rec.data.get("vpn_or_proxy_detected", False)
    device_id = tx.device_id or ""
    unknown_device = bool(device_id and known_devices and device_id not in known_devices)
    is_anomaly = unknown_device or vpn_detected

    return RuleEvaluationResult(
        rule_name="DeviceAnomalyRule",
        rule_description="Validates transaction device and VPN/proxy presence",
        passed=not is_anomaly,
        flagged=is_anomaly,
        details=f"Unknown device: {unknown_device}, VPN/Proxy: {vpn_detected}",
        severity="MEDIUM" if is_anomaly else "INFO",
        evidence_ids=[telemetry_rec.evidence_id]
    )


def evaluate_sanctions_match(records: List[EvidenceRecord]) -> RuleEvaluationResult:
    sanctions_rec = find_evidence_by_type(records, "SANCTIONS_PEP_SCREENING")
    if not sanctions_rec:
        return RuleEvaluationResult(
            rule_name="SanctionsWatchlistRule",
            rule_description="Screens counterparty and account against OFAC, PEP, and global watchlists",
            passed=True,
            flagged=False,
            details="Sanctions screening record not available",
            severity="INFO",
            evidence_ids=[]
        )
    
    match_status = sanctions_rec.data.get("match_status", "NO_MATCH")
    is_hit = match_status in ("CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT")

    return RuleEvaluationResult(
        rule_name="SanctionsWatchlistRule",
        rule_description="Screens counterparty and account against OFAC, PEP, and global watchlists",
        passed=not is_hit,
        flagged=is_hit,
        details=f"Watchlist screening status: {match_status}",
        severity="HIGH" if is_hit else "INFO",
        evidence_ids=[sanctions_rec.evidence_id]
    )


def evaluate_kyc_status(records: List[EvidenceRecord]) -> RuleEvaluationResult:
    kyc_rec = find_evidence_by_type(records, "KYC_PROFILE")
    if not kyc_rec:
        return RuleEvaluationResult(
            rule_name="KycVerificationRule",
            rule_description="Validates that customer identity verification is complete and active",
            passed=False,
            flagged=True,
            details="KYC profile record is missing",
            severity="HIGH",
            evidence_ids=[]
        )
    
    status = kyc_rec.data.get("verification_status", "UNVERIFIED")
    is_verified = (status == "VERIFIED")

    return RuleEvaluationResult(
        rule_name="KycVerificationRule",
        rule_description="Validates that customer identity verification is complete and active",
        passed=is_verified,
        flagged=not is_verified,
        details=f"KYC verification status: {status}",
        severity="HIGH" if not is_verified else "INFO",
        evidence_ids=[kyc_rec.evidence_id]
    )


def run_all_deterministic_rules(case: InvestigationCase) -> List[RuleEvaluationResult]:
    """Execute all deterministic rules against a case."""
    results = [
        evaluate_large_amount(case.transaction),
        evaluate_structuring(case.transaction),
        evaluate_high_risk_jurisdiction(case.transaction),
        evaluate_velocity_anomaly(case.transaction, case.evidence_records),
        evaluate_device_anomaly(case.transaction, case.evidence_records),
        evaluate_sanctions_match(case.evidence_records),
        evaluate_kyc_status(case.evidence_records),
    ]
    return results
