"""
Deterministic transaction risk rules for Ceylix AI.
These rules run explicitly over case data to provide transparent, inspectable risk signals.
"""

from typing import List, Dict, Any, Optional, Tuple
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
        rule_description=f"Flags wire transfers exceeding ${LARGE_AMOUNT_THRESHOLD:,.2f} USD equivalent (Large Wire Monitoring Threshold - BSA Travel Rule recordkeeping advisory; Note: FinCEN CTR Form 112 applies only to physical currency/cash)",
        dimension="FINANCIAL_TRANSACTION_RISK",
        passed=not is_large,
        flagged=is_large,
        details=f"Transaction amount ${tx.amount:,.2f} {tx.currency} (Exceeds $10,000 Large Wire Monitoring threshold - BSA Travel Rule recordkeeping advisory; does not require physical currency CTR Form 112 filing unless settled in cash)",
        severity="INFO",
        evidence_ids=[]
    )



def evaluate_structuring(tx: Transaction) -> RuleEvaluationResult:
    is_structuring = STRUCTURING_LOWER_BOUND <= tx.amount <= STRUCTURING_UPPER_BOUND
    return RuleEvaluationResult(
        rule_name="StructuringSmurfingRule",
        rule_description="Flags transactions just below the $10,000 threshold (potential structuring / smurfing advisory)",
        dimension="FINANCIAL_TRANSACTION_RISK",
        passed=not is_structuring,
        flagged=is_structuring,
        details=f"Amount ${tx.amount:,.2f} in range [${STRUCTURING_LOWER_BOUND:,.2f}, ${STRUCTURING_UPPER_BOUND:,.2f}] (Advisory monitoring for structured amounts)",
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


def calculate_authoritative_risk_score(
    case: InvestigationCase,
    rule_results: List[RuleEvaluationResult],
    val_report: Optional[Any] = None,
    intent_result: Optional[Any] = None,
    probes: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Authoritative, deterministic, reproducible risk scoring engine for Ceylix AI.
    BFSI Compliance Policy Version: 2026.1-REGULATORY-DETERMINISTIC.

    Formula and component weights:
      - Base baseline: 5
      - Sanctions match: +60 (confirmed entity match), +35 (potential/PEP), +15 (missing mandatory screening)
      - Jurisdiction: +25 (FATF high-risk blacklist)
      - Amount & Structuring:
          * Intentional structuring ($9k-$10k): +30
          * CTR reporting threshold ($10k-$50k): +10
          * Elevated wire ($50k-$250k): +15
          * High-value international wire (> $250k): +20
          * Low-value domestic retail (< $500): -5
      - Customer KYC: +20 (unverified KYC on >= $500)
      - Velocity Anomaly: +15 (> 5x 30d baseline)
      - Device Telemetry: +15 (proxy/VPN anonymization; 0 for clean or RFC 5737 test IP)
      - Adversarial Injection: +40 (prompt injection attack detected)
      - Content/Intent Mismatch: +5 (non-financial administrative mismatch)

    Returns:
      (authoritative_score: int, score_breakdown: Dict[str, Any])
    """
    tx = case.transaction
    components: Dict[str, Dict[str, Any]] = {}
    total_score = 5
    components["base_baseline"] = {"points": 5, "rationale": "Standard baseline transactional scrutiny"}

    # 1. Sanctions screening component
    bound_records = [
        record for record in case.evidence_records
        if evidence_belongs_to_case(record, case)
    ]
    sanctions_rec = find_evidence_by_type(bound_records, "SANCTIONS_PEP_SCREENING")
    match_status = (
        usable_entity_sanctions_status(sanctions_rec, tx)
        if sanctions_rec else "UNKNOWN"
    )
    is_confirmed_hit = (match_status == "CONFIRMED_MATCH")
    is_potential_hit = (match_status in ("POTENTIAL_MATCH", "PEP_HIT"))

    # Missing mandatory screening check on high-value wires (>= $10,000)
    is_mandatory_screening_missing = (
        tx.amount >= 10000.0
        and (sanctions_rec is None or match_status == "UNKNOWN")
        and (not sanctions_rec or sanctions_rec.data.get("match_status") != "NO_MATCH")
    )

    if is_confirmed_hit:
        total_score += 60
        components["sanctions_screening"] = {
            "points": 60,
            "status": "CONFIRMED_MATCH",
            "rationale": "Authoritative confirmed entity sanctions match on OFAC/Watchlist",
        }
    elif is_potential_hit:
        total_score += 35
        components["sanctions_screening"] = {
            "points": 35,
            "status": match_status,
            "rationale": f"Watchlist screening hit flagged: {match_status}",
        }
    elif is_mandatory_screening_missing:
        total_score += 15
        components["sanctions_screening"] = {
            "points": 15,
            "status": "MISSING_MANDATORY_SCREENING",
            "rationale": "Mandatory sanctions screening unavailable for international/high-value wire (regulatory due diligence requirement)",
        }
    else:
        components["sanctions_screening"] = {
            "points": 0,
            "status": "CLEAR" if match_status == "NO_MATCH" else "UNKNOWN",
            "rationale": "No confirmed or potential entity sanctions match",
        }

    # 2. Jurisdiction component
    c_country = tx.counterparty_country.upper()
    is_embargoed_country = c_country in {"IR", "KP", "SY", "CU"}
    is_high_risk_country = c_country in HIGH_RISK_JURISDICTIONS
    if is_embargoed_country:
        total_score += 65
        components["corridor_jurisdiction"] = {
            "points": 65,
            "country": tx.counterparty_country,
            "rationale": f"Comprehensively sanctioned / embargoed jurisdiction ({tx.counterparty_country}) under OFAC/FATF blacklist",
        }
    elif is_high_risk_country:
        total_score += 25
        components["corridor_jurisdiction"] = {
            "points": 25,
            "country": tx.counterparty_country,
            "rationale": f"High-risk / secrecy jurisdiction ({tx.counterparty_country}) on FATF watchlist",
        }
    else:
        components["corridor_jurisdiction"] = {
            "points": 0,
            "country": tx.counterparty_country,
            "rationale": f"Standard compliant corridor ({tx.origin_country or 'US'} -> {tx.counterparty_country})",
        }

    # 3. Financial Amount and Structuring component
    is_structuring = (STRUCTURING_LOWER_BOUND <= tx.amount <= STRUCTURING_UPPER_BOUND)
    is_domestic = (tx.origin_country or "US").upper() == (tx.counterparty_country or "US").upper()
    if is_structuring:
        total_score += 30
        components["amount_and_structuring"] = {
            "points": 30,
            "amount": tx.amount,
            "rationale": "Transaction amount structured just below $10,000 threshold (potential smurfing/structuring advisory)",
        }
    elif tx.amount < 500.0 and is_domestic:
        total_score -= 5
        components["amount_and_structuring"] = {
            "points": -5,
            "amount": tx.amount,
            "rationale": "Low-value domestic retail transaction (< $500.00) qualifying for reflex clearance discount",
        }
    elif tx.amount > 250000.0:
        total_score += 20
        components["amount_and_structuring"] = {
            "points": 20,
            "amount": tx.amount,
            "rationale": "High-value international wire (> $250,000.00 EDD threshold) requiring enhanced due diligence",
        }
    elif tx.amount >= 50000.0:
        total_score += 15
        components["amount_and_structuring"] = {
            "points": 15,
            "amount": tx.amount,
            "rationale": "Elevated wire amount ($50,000 - $250,000) under large-value wire monitoring",
        }
    elif tx.amount >= 10000.0:
        total_score += 10
        components["amount_and_structuring"] = {
            "points": 10,
            "amount": tx.amount,
            "rationale": "Exceeds $10,000 large-value wire threshold (BSA Travel Rule recordkeeping advisory; CTR Form 112 applies strictly to physical cash)",
        }
    else:
        components["amount_and_structuring"] = {
            "points": 0,
            "amount": tx.amount,
            "rationale": "Sub-threshold transaction amount within normal limits",
        }

    # 4. Customer KYC component
    kyc_rec = find_evidence_by_type(bound_records, "KYC_PROFILE")
    kyc_status = kyc_rec.data.get("verification_status", "UNVERIFIED") if kyc_rec else "UNVERIFIED"
    if kyc_status != "VERIFIED" and tx.amount >= 500.0 and kyc_rec is not None:
        total_score += 20
        components["customer_kyc"] = {
            "points": 20,
            "status": kyc_status,
            "rationale": f"Customer KYC profile verification status is '{kyc_status}' on transaction >= $500",
        }
    else:
        components["customer_kyc"] = {
            "points": 0,
            "status": kyc_status if kyc_rec else "OMITTED_OPTIONAL",
            "rationale": "Customer KYC profile verified or within standard parameters",
        }

    # 5. Velocity anomaly component
    history_rec = find_evidence_by_type(bound_records, "ACCOUNT_HISTORY")
    avg_amount = float(history_rec.data.get("avg_30d_transaction_amount", 1000.0)) if history_rec else 1000.0
    is_velocity = (tx.amount >= 500.0 and avg_amount > 0 and tx.amount / avg_amount >= 5.0)
    if is_velocity:
        total_score += 15
        components["velocity_anomaly"] = {
            "points": 15,
            "ratio": round(tx.amount / avg_amount, 1),
            "rationale": f"Transaction volume {tx.amount / avg_amount:.1f}x higher than 30-day baseline average",
        }
    else:
        components["velocity_anomaly"] = {
            "points": 0,
            "rationale": "Transaction velocity consistent with historical baseline",
        }

    # 6. Device & Network Telemetry component
    telemetry_rec = find_evidence_by_type(bound_records, "DEVICE_IP_TELEMETRY")
    ip_str = tx.ip_address or (telemetry_rec.data.get("ip_address") if telemetry_rec else "")
    vpn_active = telemetry_rec.data.get("vpn_or_proxy_detected", False) if telemetry_rec else False
    if not vpn_active and ip_str and (ip_str.startswith("185.220.") or ip_str.startswith("103.251.")):
        vpn_active = True

    if vpn_active:
        total_score += 15
        components["device_telemetry"] = {
            "points": 15,
            "ip": ip_str,
            "rationale": "Proxy / VPN anonymization detected on client IP (network routing risk; does not prove financial crime)",
        }
    else:
        components["device_telemetry"] = {
            "points": 0,
            "ip": ip_str,
            "rationale": "Clean IP routing or RFC 5737 documentation test fixture",
        }

    # 7. Adversarial untrusted instructions
    if val_report and val_report.untrusted_instruction_detected:
        total_score += 40
        components["adversarial_injection"] = {
            "points": 40,
            "rationale": "Adversarial system override or prompt injection attempt detected in payment instruction",
        }
    else:
        components["adversarial_injection"] = {
            "points": 0,
            "rationale": "No prompt injection or adversarial override tokens detected",
        }

    # 8. Content / Intent Mismatch
    if intent_result and not intent_result.is_compatible_with_financial_triage:
        total_score += 5
        components["intent_mismatch"] = {
            "points": 5,
            "intent": intent_result.intent,
            "rationale": f"Payment instruction text contains unrelated {intent_result.intent} content (quarantined)",
        }
    else:
        components["intent_mismatch"] = {
            "points": 0,
            "rationale": "Valid financial transaction instruction format",
        }

    clamped_score = max(0, min(100, total_score))
    risk_level = "LOW" if clamped_score < 30 else ("MEDIUM" if clamped_score < 70 else "HIGH")

    breakdown = {
        "policy_version": "2026.1-REGULATORY-DETERMINISTIC",
        "authoritative_score": clamped_score,
        "preliminary_risk_level": risk_level,
        "base_score": 5,
        "components": components,
    }

    return clamped_score, breakdown

