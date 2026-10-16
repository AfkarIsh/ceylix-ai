"""
Deterministic Evidence Validator for Ceylix AI.
Validates LLM-generated claims against recorded case evidence, checks for staleness,
contradictions, missing mandatory evidence, and adversarial untrusted instructions.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import re
try:
    from backend.app.schemas import (
        InvestigationCase,
        EvidenceRecord,
        Claim,
        Transaction,
    )
except ModuleNotFoundError:
    from app.schemas import (
        InvestigationCase,
        EvidenceRecord,
        Claim,
        Transaction,
    )

# Maximum allowable age (in days) before evidence is classified as STALE
EVIDENCE_FRESHNESS_LIMITS_DAYS: Dict[str, float] = {
    "KYC_PROFILE": 730.0,            # 2 years
    "SANCTIONS_PEP_SCREENING": 1.0,   # 24 hours
    "DEVICE_IP_TELEMETRY": 90.0,      # 3 months
    "COUNTERPARTY_REPUTATION": 180.0, # 6 months
    "ACCOUNT_HISTORY": 30.0,          # 1 month
    "TERMINAL_LOCATION_LOG": 7.0,     # 7 days
    "INVOICE_RECEIPT": 60.0,          # 60 days
}

# Injection indicators in untrusted inputs
PROMPT_INJECTION_PATTERNS = [
    r"\[SYSTEM OVERRIDE\]",
    r"IGNORE (ALL )?PREVIOUS (INSTRUCTIONS|RULES|FLAGS)",
    r"DISREGARD (PRIOR|ALL) (AML|FRAUD|TRANSACTION|DEVICE)",
    r"SUPERVISOR OVERRIDE",
    r"BOARD OF DIRECTORS (OVERRIDE|VERIFIED)",
    r"EXECUTIVE TREATY",
    r"MARK (RISK AS )?LOW",
    r"RETURN VERDICT BENIGN",
    r"DO NOT FLAG",
    r"EXEMPT FROM (KYC|AML|SCREENING)",
    r"SET SUPPORT_STATUS",
    r"INSTRUCTION FOR AI (MODEL|ASSISTANT)",
]


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime safely with UTC fallback."""
    clean_str = dt_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


class ValidationReport:
    """Detailed summary of the deterministic validation phase."""
    def __init__(self):
        self.validated_claims: List[Claim] = []
        self.unsupported_claims_count: int = 0
        self.stale_claims_count: int = 0
        self.conflicting_claims_count: int = 0
        self.total_claims_count: int = 0
        self.traceable_claims_count: int = 0
        self.stale_evidence_ids: List[str] = []
        self.detected_conflicts: List[Dict[str, Any]] = []
        self.missing_required_evidence: List[str] = []
        self.untrusted_instruction_detected: bool = False
        self.untrusted_instruction_details: List[str] = []
        self.validation_warnings: List[str] = []


def detect_untrusted_instructions(case: InvestigationCase) -> Tuple[bool, List[str]]:
    """Scan untrusted user-supplied fields for prompt injection attempts."""
    detected = False
    details = []

    fields_to_check = [
        ("transaction.memo", case.transaction.memo or ""),
        ("transaction.counterparty_name", case.transaction.counterparty_name or ""),
    ]

    for rec in case.evidence_records:
        if rec.evidence_type == "INVOICE_RECEIPT":
            desc = rec.data.get("description", "")
            fields_to_check.append((f"{rec.evidence_id}.description", desc))
        elif rec.evidence_type == "COUNTERPARTY_REPUTATION":
            notes = rec.data.get("notes", "")
            fields_to_check.append((f"{rec.evidence_id}.notes", notes))

    for field_name, text in fields_to_check:
        for pat in PROMPT_INJECTION_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                detected = True
                details.append(f"Adversarial instruction pattern '{pat}' detected in {field_name}")

    return detected, details


def check_evidence_freshness(case: InvestigationCase) -> List[Tuple[str, str, float]]:
    """Identify evidence records exceeding allowed age SLA relative to transaction timestamp."""
    tx_time = parse_iso_datetime(case.transaction.timestamp)
    stale_items = []

    for rec in case.evidence_records:
        limit_days = EVIDENCE_FRESHNESS_LIMITS_DAYS.get(rec.evidence_type)
        if limit_days is None:
            continue
        rec_time = parse_iso_datetime(rec.timestamp)
        age_days = (tx_time - rec_time).total_seconds() / 86400.0

        if age_days > limit_days:
            stale_items.append((rec.evidence_id, rec.evidence_type, age_days))

    return stale_items


def check_evidence_contradictions(case: InvestigationCase) -> List[Dict[str, Any]]:
    """Detect logical or physical contradictions across recorded evidence."""
    conflicts = []
    records_by_type = {r.evidence_type: r for r in case.evidence_records}

    # 1. Location contradiction (Terminal tap vs IP/Device location)
    terminal_rec = records_by_type.get("TERMINAL_LOCATION_LOG")
    device_rec = records_by_type.get("DEVICE_IP_TELEMETRY")
    if terminal_rec and device_rec:
        term_city = terminal_rec.data.get("city", "").lower()
        dev_city = device_rec.data.get("ip_city", "").lower()
        term_time = parse_iso_datetime(terminal_rec.timestamp)
        dev_time = parse_iso_datetime(device_rec.timestamp)
        diff_hours = abs((term_time - dev_time).total_seconds()) / 3600.0

        if term_city and dev_city and term_city != dev_city and diff_hours < 2.0:
            conflicts.append({
                "type": "IMPOSSIBLE_TRAVEL_CONTRADICTION",
                "evidence_ids": [terminal_rec.evidence_id, device_rec.evidence_id],
                "description": f"Physical terminal in {term_city} contradicts IP session in {dev_city} within {diff_hours:.1f} hours"
            })

    # 2. Amount contradiction (Ledger amount vs Invoice / Receipt)
    invoice_rec = records_by_type.get("INVOICE_RECEIPT")
    if invoice_rec:
        inv_amount = float(invoice_rec.data.get("amount", 0.0))
        tx_amount = float(case.transaction.amount)
        if inv_amount > 0 and abs(inv_amount - tx_amount) > (0.05 * tx_amount):
            conflicts.append({
                "type": "AMOUNT_MISMATCH_CONTRADICTION",
                "evidence_ids": [invoice_rec.evidence_id, case.transaction.transaction_id],
                "description": f"Transaction amount ${tx_amount:,.2f} contradicts invoice document ${inv_amount:,.2f}"
            })

    # 3. Residence / KYC contradiction
    kyc_rec = records_by_type.get("KYC_PROFILE")
    history_rec = records_by_type.get("ACCOUNT_HISTORY")
    if kyc_rec and history_rec:
        kyc_country = kyc_rec.data.get("country_of_residence", "").upper()
        hist_notes = history_rec.data.get("residence_remarks", "").upper()
        if kyc_country and hist_notes and ("RESIDENT IN " in hist_notes) and (kyc_country not in hist_notes):
            conflicts.append({
                "type": "RESIDENCE_DATA_CONTRADICTION",
                "evidence_ids": [kyc_rec.evidence_id, history_rec.evidence_id],
                "description": f"KYC country ({kyc_country}) contradicts account history remarks ({hist_notes})"
            })

    # 4. Sanctions screening contradictory feeds
    sanctions_rec = records_by_type.get("SANCTIONS_PEP_SCREENING")
    if sanctions_rec:
        feed_a = sanctions_rec.data.get("feed_a_status")
        feed_b = sanctions_rec.data.get("feed_b_status")
        if feed_a and feed_b and feed_a != feed_b:
            conflicts.append({
                "type": "SANCTIONS_FEED_CONTRADICTION",
                "evidence_ids": [sanctions_rec.evidence_id],
                "description": f"Sanctions feed A ({feed_a}) directly contradicts feed B ({feed_b})"
            })

    return conflicts


def check_missing_required_evidence(case: InvestigationCase) -> List[str]:
    """Check mandatory evidence types per regulatory risk policy."""
    missing = []
    available_types = {r.evidence_type for r in case.evidence_records}

    # Policy: High value wires (>= $10,000) or international wires require KYC and Sanctions screening
    is_high_value = case.transaction.amount >= 10000.0
    is_wire = "WIRE" in case.transaction.channel.upper()

    if is_high_value or is_wire:
        if "KYC_PROFILE" not in available_types:
            missing.append("KYC_PROFILE")
        if "SANCTIONS_PEP_SCREENING" not in available_types:
            missing.append("SANCTIONS_PEP_SCREENING")

    # Policy: Remote channels require device or IP telemetry
    if case.transaction.channel in ("ONLINE_BANKING", "MOBILE_APP", "CARD_NOT_PRESENT"):
        if "DEVICE_IP_TELEMETRY" not in available_types:
            missing.append("DEVICE_IP_TELEMETRY")

    return missing


def validate_claims(
    case: InvestigationCase,
    raw_claims: List[Claim],
    injection_detected: bool,
    stale_ids: List[str],
    conflict_map: Dict[str, Dict[str, Any]],
) -> List[Claim]:
    """Validate each claim against recorded case evidence."""
    evidence_id_map: Dict[str, EvidenceRecord] = {r.evidence_id: r for r in case.evidence_records}
    tx_id = case.transaction.transaction_id
    validated: List[Claim] = []

    for claim in raw_claims:
        v_claim = claim.model_copy()
        
        # 1. Evidence ID verification
        if not v_claim.evidence_ids:
            # Claims asserting facts without citing evidence are unsupported
            if v_claim.claim_type in ("factual_assertion", "rule_result"):
                v_claim.support_status = "unsupported"
                v_claim.review_required = True
                v_claim.validation_notes = "Claim asserts factual or rule outcome without citing evidence IDs."
                validated.append(v_claim)
                continue

        # Check if all cited IDs exist
        non_existent_ids = [
            eid for eid in v_claim.evidence_ids
            if eid != tx_id and eid not in evidence_id_map
        ]
        if non_existent_ids:
            v_claim.support_status = "unsupported"
            v_claim.review_required = True
            v_claim.validation_notes = f"Referenced non-existent evidence IDs: {non_existent_ids}"
            validated.append(v_claim)
            continue

        # 2. Check if claim relies on stale evidence
        c_stale_ids = [eid for eid in v_claim.evidence_ids if eid in stale_ids]
        if c_stale_ids:
            v_claim.support_status = "stale"
            v_claim.review_required = True
            v_claim.validation_notes = f"Evidence ID(s) {c_stale_ids} exceed validity freshness limit."
            validated.append(v_claim)
            continue

        # 3. Check if claim relies on conflicting evidence
        c_conflict = None
        for eid in v_claim.evidence_ids:
            if eid in conflict_map:
                c_conflict = conflict_map[eid]
                break
        if c_conflict:
            v_claim.support_status = "conflicting"
            v_claim.review_required = True
            v_claim.validation_notes = f"Contradiction detected: {c_conflict['description']}"
            validated.append(v_claim)
            continue

        # 4. Check if claim adopted untrusted prompt injection assertions
        if injection_detected:
            text_lower = v_claim.text.lower()
            if any(term in text_lower for term in [
                "exempt", "board of directors", "executive treaty", "override",
                "disregard", "cleared by admin", "safe to ignore"
            ]):
                v_claim.support_status = "unsupported"
                v_claim.review_required = True
                v_claim.validation_notes = "Claim echoes untrusted injection instruction from input payload."
                validated.append(v_claim)
                continue

        # 5. Semantic field reference check if provided
        if v_claim.field_references:
            field_mismatch = False
            mismatch_detail = ""
            for fref in v_claim.field_references:
                ref_id = fref.get("evidence_id")
                field_name = fref.get("field")
                claimed_val = fref.get("value")

                if ref_id == tx_id:
                    tx_dict = case.transaction.model_dump()
                    actual_val = tx_dict.get(field_name)
                    if actual_val is None or (isinstance(actual_val, (int, float)) and abs(actual_val - claimed_val) > 0.01):
                        field_mismatch = True
                        mismatch_detail = f"Field '{field_name}' claimed {claimed_val} != actual {actual_val}"
                        break
                elif ref_id in evidence_id_map:
                    rec_data = evidence_id_map[ref_id].data
                    actual_val = rec_data.get(field_name)
                    if actual_val is None or (isinstance(actual_val, (int, float)) and abs(actual_val - claimed_val) > 0.01):
                        field_mismatch = True
                        mismatch_detail = f"Evidence {ref_id} field '{field_name}' claimed {claimed_val} != actual {actual_val}"
                        break

            if field_mismatch:
                v_claim.support_status = "unsupported"
                v_claim.review_required = True
                v_claim.validation_notes = mismatch_detail
                validated.append(v_claim)
                continue

        # Otherwise claim is supported
        v_claim.support_status = "supported"
        v_claim.review_required = False
        v_claim.validation_notes = "Verified against recorded evidence."
        validated.append(v_claim)

    return validated


def perform_deterministic_validation(
    case: InvestigationCase,
    raw_claims: List[Claim]
) -> ValidationReport:
    """Run full deterministic validation suite over a case and its claims."""
    report = ValidationReport()
    report.total_claims_count = len(raw_claims)

    # 1. Untrusted instructions
    inj_detected, inj_details = detect_untrusted_instructions(case)
    report.untrusted_instruction_detected = inj_detected
    report.untrusted_instruction_details = inj_details

    # 2. Staleness
    stale_tuples = check_evidence_freshness(case)
    report.stale_evidence_ids = [t[0] for t in stale_tuples]
    for eid, etype, age in stale_tuples:
        report.validation_warnings.append(
            f"Stale evidence {eid} ({etype}): age {age:.1f} days exceeds SLA threshold."
        )

    # 3. Contradictions
    conflicts = check_evidence_contradictions(case)
    report.detected_conflicts = conflicts
    conflict_map = {}
    for c in conflicts:
        for eid in c["evidence_ids"]:
            conflict_map[eid] = c
        report.validation_warnings.append(f"Contradiction: {c['description']}")

    # 4. Missing required evidence
    missing_req = check_missing_required_evidence(case)
    report.missing_required_evidence = missing_req
    for m in missing_req:
        report.validation_warnings.append(f"Missing mandatory evidence type: {m}")

    # 5. Claim validation
    report.validated_claims = validate_claims(
        case=case,
        raw_claims=raw_claims,
        injection_detected=inj_detected,
        stale_ids=report.stale_evidence_ids,
        conflict_map=conflict_map,
    )

    # 6. Aggregate counts
    evidence_id_set = {r.evidence_id for r in case.evidence_records} | {case.transaction.transaction_id}
    for c in report.validated_claims:
        if c.support_status == "unsupported":
            report.unsupported_claims_count += 1
        elif c.support_status == "stale":
            report.stale_claims_count += 1
        elif c.support_status == "conflicting":
            report.conflicting_claims_count += 1
        
        # Traceability: claim cites valid existing evidence ID(s)
        if c.evidence_ids and all(eid in evidence_id_set for eid in c.evidence_ids):
            report.traceable_claims_count += 1

    return report
