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
        RiskDimensionBreakdown,
    )
    from backend.app.evidence_validator import (
        evidence_belongs_to_case,
        usable_entity_sanctions_status,
    )
except ModuleNotFoundError:
    from app.schemas import (
        Transaction,
        EvidenceRecord,
        RuleEvaluationResult,
        InvestigationCase,
        RiskDimensionBreakdown,
    )
    from app.evidence_validator import (
        evidence_belongs_to_case,
        usable_entity_sanctions_status,
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
        dimension="FINANCIAL_TRANSACTION_RISK",
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
        dimension="FINANCIAL_TRANSACTION_RISK",
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
        dimension="SANCTIONS_WATCHLIST_RISK",
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
            dimension="BEHAVIORAL_VELOCITY_RISK",
            passed=True,
            flagged=False,
            details="Account history record not available for velocity evaluation",
            severity="INFO",
            evidence_ids=[]
        )
    
    avg_amount = float(history_rec.data.get("avg_30d_transaction_amount", 1000.0))
    ratio = tx.amount / avg_amount if avg_amount > 0 else 1.0

    # Suppress velocity anomaly penalties on low-value retail transactions under $500
    if tx.amount < 500.0:
        return RuleEvaluationResult(
            rule_name="VelocityAnomalyRule",
            rule_description="Compares transaction amount against 30-day historical average volume (>5x baseline)",
            dimension="BEHAVIORAL_VELOCITY_RISK",
            passed=True,
            flagged=False,
            details=f"Transaction amount ${tx.amount:,.2f} is under $500.00 retail baseline threshold",
            severity="INFO",
            evidence_ids=[history_rec.evidence_id]
        )

    is_anomaly = ratio >= 5.0

    return RuleEvaluationResult(
        rule_name="VelocityAnomalyRule",
        rule_description="Compares transaction amount against 30-day historical average volume (>5x baseline)",
        dimension="BEHAVIORAL_VELOCITY_RISK",
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
            dimension="DEVICE_NETWORK_RISK",
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
        dimension="DEVICE_NETWORK_RISK",
        passed=not is_anomaly,
        flagged=is_anomaly,
        details=f"Unknown device: {unknown_device}, VPN/Proxy: {vpn_detected}",
        severity="MEDIUM" if is_anomaly else "INFO",
        evidence_ids=[telemetry_rec.evidence_id]
    )


def evaluate_sanctions_match(
    records: List[EvidenceRecord],
    transaction: Optional[Transaction] = None,
) -> RuleEvaluationResult:
    sanctions_rec = find_evidence_by_type(records, "SANCTIONS_PEP_SCREENING")
    if not sanctions_rec:
        return RuleEvaluationResult(
            rule_name="SanctionsWatchlistRule",
            rule_description="Screens counterparty and account against OFAC, PEP, and global watchlists",
            dimension="SANCTIONS_WATCHLIST_RISK",
            passed=True,
            flagged=False,
            details="Sanctions screening record not available",
            severity="INFO",
            evidence_ids=[]
        )
    
    match_status = (
        usable_entity_sanctions_status(sanctions_rec, transaction)
        if transaction is not None else "UNKNOWN"
    )
    is_hit = match_status in ("CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT")

    return RuleEvaluationResult(
        rule_name="SanctionsWatchlistRule",
        rule_description="Screens counterparty and account against OFAC, PEP, and global watchlists",
        dimension="SANCTIONS_WATCHLIST_RISK",
        passed=not is_hit,
        flagged=is_hit,
        details=f"Watchlist screening status: {match_status}",
        severity="HIGH" if is_hit else "INFO",
        evidence_ids=[sanctions_rec.evidence_id]
    )


def evaluate_kyc_status(records: List[EvidenceRecord], tx: Optional[Transaction] = None) -> RuleEvaluationResult:
    kyc_rec = find_evidence_by_type(records, "KYC_PROFILE")
    if not kyc_rec:
        # Missing optional KYC evidence must not be treated as a confirmed fraudulent or adverse finding.
        # Assign severity "INFO" so missing optional evidence does not trigger a 94/100 CRITICAL escalation state.
        return RuleEvaluationResult(
            rule_name="KycVerificationRule",
            rule_description="Validates that customer identity verification is complete and active",
            dimension="CUSTOMER_KYC_RISK",
            passed=True,
            flagged=False,
            details="KYC profile record is not available (optional baseline omitted)",
            severity="INFO",
            evidence_ids=[]
        )
    
    status = kyc_rec.data.get("verification_status", "UNVERIFIED")
    is_verified = (status == "VERIFIED")

    # If low-value transaction (< 500.0) has unverified KYC, assign LOW severity instead of HIGH
    severity = "HIGH"
    if not is_verified and tx and tx.amount < 500.0:
        severity = "LOW"
    elif is_verified:
        severity = "INFO"

    return RuleEvaluationResult(
        rule_name="KycVerificationRule",
        rule_description="Validates that customer identity verification is complete and active",
        dimension="CUSTOMER_KYC_RISK",
        passed=is_verified,
        flagged=not is_verified,
        details=f"KYC verification status: {status}",
        severity=severity,
        evidence_ids=[kyc_rec.evidence_id]
    )


def run_all_deterministic_rules(case: InvestigationCase) -> List[RuleEvaluationResult]:
    """Execute all deterministic rules against a case."""
    bound_records = [
        record for record in case.evidence_records
        if evidence_belongs_to_case(record, case)
    ]
    results = [
        evaluate_large_amount(case.transaction),
        evaluate_structuring(case.transaction),
        evaluate_high_risk_jurisdiction(case.transaction),
        evaluate_velocity_anomaly(case.transaction, bound_records),
        evaluate_device_anomaly(case.transaction, bound_records),
        evaluate_sanctions_match(bound_records, case.transaction),
        evaluate_kyc_status(bound_records, case.transaction),
    ]
    return results


def build_risk_dimension_breakdown(
    case: InvestigationCase,
    rule_results: List[RuleEvaluationResult],
    val_report: Optional[Any] = None,
    intent_result: Optional[Any] = None,
) -> RiskDimensionBreakdown:
    """
    Construct multi-dimensional risk breakdown preserving dimensional separation.
    Prevents premature score collapse across independent risk verticals.
    """
    tx = case.transaction

    # 1. Financial transaction risk
    fin_rules = [r for r in rule_results if r.dimension == "FINANCIAL_TRANSACTION_RISK"]
    fin_flagged = any(r.flagged for r in fin_rules)
    fin_status = "FLAGGED" if fin_flagged else "CLEAR"
    fin_risk = {
        "status": fin_status,
        "amount": tx.amount,
        "currency": tx.currency,
        "large_amount_threshold": LARGE_AMOUNT_THRESHOLD,
        "structuring_range": [STRUCTURING_LOWER_BOUND, STRUCTURING_UPPER_BOUND],
        "rules": [r.model_dump() for r in fin_rules],
    }

    # 2. Sanctions and watchlist findings
    sanc_rules = [r for r in rule_results if r.dimension == "SANCTIONS_WATCHLIST_RISK"]
    entity_sanctions_flagged = any(
        r.flagged and r.rule_name == "SanctionsWatchlistRule"
        for r in sanc_rules
    )
    bound_records = [
        record for record in case.evidence_records
        if evidence_belongs_to_case(record, case)
    ]
    sanctions_rec = find_evidence_by_type(bound_records, "SANCTIONS_PEP_SCREENING")
    match_status = (
        usable_entity_sanctions_status(sanctions_rec, tx)
        if sanctions_rec else "UNKNOWN"
    )
    sanc_status = (
        "MATCHED"
        if entity_sanctions_flagged
        else ("CLEAR" if match_status == "NO_MATCH" else "UNKNOWN")
    )
    sanc_risk = {
        "status": sanc_status,
        "match_status": match_status,
        "corridor": f"{tx.origin_country or 'US'} -> {tx.counterparty_country}",
        "counterparty_name": tx.counterparty_name,
        "is_high_risk_jurisdiction": tx.counterparty_country.upper() in HIGH_RISK_JURISDICTIONS,
        "corridor_risk_status": (
            "HIGH" if tx.counterparty_country.upper() in HIGH_RISK_JURISDICTIONS else "CLEAR"
        ),
        "rules": [r.model_dump() for r in sanc_rules],
    }

    # 3. Customer / KYC risk
    kyc_rules = [r for r in rule_results if r.dimension == "CUSTOMER_KYC_RISK"]
    kyc_rec = find_evidence_by_type(case.evidence_records, "KYC_PROFILE")
    kyc_status = kyc_rec.data.get("verification_status", "UNKNOWN") if kyc_rec else "UNKNOWN"
    kyc_risk = {
        "status": kyc_status,
        "customer_id": tx.customer_id or tx.account_id,
        "rules": [r.model_dump() for r in kyc_rules],
    }

    # 4. Behavioral and velocity anomalies
    vel_rules = [r for r in rule_results if r.dimension == "BEHAVIORAL_VELOCITY_RISK"]
    vel_flagged = any(r.flagged for r in vel_rules)
    vel_risk = {
        "status": "FLAGGED" if vel_flagged else "NORMAL",
        "rules": [r.model_dump() for r in vel_rules],
    }

    # 5. Device, IP, and network indicators
    dev_rules = [r for r in rule_results if r.dimension == "DEVICE_NETWORK_RISK"]
    dev_flagged = any(r.flagged for r in dev_rules)
    dev_risk = {
        "status": "FLAGGED" if dev_flagged else "CLEAR",
        "rules": [r.model_dump() for r in dev_rules],
    }

    bank_text = (tx.counterparty_bank or "").upper()
    bank_risk = {
        "status": "REVIEW" if any(term in bank_text for term in ("TEHRAN", "MELLAT", "PYONGYANG")) else "UNKNOWN",
        "counterparty_bank": tx.counterparty_bank,
        "note": "Bank risk is independent of beneficiary country and entity sanctions status.",
    }

    # 6. Data quality and input mismatch
    if intent_result:
        data_quality = {
            "intent": intent_result.intent,
            "compatible": intent_result.is_compatible_with_financial_triage,
            "mismatch_detected": not intent_result.is_compatible_with_financial_triage,
            "routing_target": intent_result.routing_target,
            "warnings": intent_result.warnings,
        }
    else:
        data_quality = {
            "intent": "TRANSACTION_INVESTIGATION",
            "compatible": True,
            "mismatch_detected": False,
            "routing_target": "bfsi_forensic_investigation_workflow",
            "warnings": [],
        }

    # 7. Evidence completeness and confidence
    if val_report:
        grounding_status = "FULLY_GROUNDED"
        if val_report.untrusted_instruction_detected or val_report.unsupported_claims_count > 0 or val_report.conflicting_claims_count > 0:
            grounding_status = "UNGROUNDED"
        elif val_report.stale_claims_count > 0 or val_report.missing_required_evidence:
            grounding_status = "PARTIALLY_GROUNDED"

        evidence_confidence = {
            "grounding_status": grounding_status,
            "total_claims": val_report.total_claims_count,
            "unsupported_claims": val_report.unsupported_claims_count,
            "stale_claims": val_report.stale_claims_count,
            "conflicting_claims": val_report.conflicting_claims_count,
            "missing_mandatory_evidence": val_report.missing_required_evidence,
            "untrusted_instruction_detected": val_report.untrusted_instruction_detected,
        }
    else:
        evidence_confidence = {
            "grounding_status": "FULLY_GROUNDED",
            "total_claims": 0,
            "unsupported_claims": 0,
            "stale_claims": 0,
            "conflicting_claims": 0,
            "missing_mandatory_evidence": [],
            "untrusted_instruction_detected": False,
        }

    return RiskDimensionBreakdown(
        financial_transaction_risk=fin_risk,
        sanctions_watchlist_risk=sanc_risk,
        customer_kyc_risk=kyc_risk,
        behavioral_velocity_risk=vel_risk,
        device_network_risk=dev_risk,
        bank_risk=bank_risk,
        data_quality_input_intent=data_quality,
        evidence_completeness_confidence=evidence_confidence,
    )
