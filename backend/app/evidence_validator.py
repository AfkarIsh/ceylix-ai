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


def evidence_belongs_to_transaction(
    record: EvidenceRecord,
    transaction: Transaction,
) -> bool:
    """Require every explicit transaction/customer binding to match exactly."""
    bound_transaction = record.transaction_id or record.data.get("transaction_id")
    bound_customer = record.customer_id or record.data.get("customer_id")
    return (
        (bound_transaction is None or str(bound_transaction) == transaction.transaction_id)
        and (bound_customer is None or str(bound_customer) == transaction.customer_id)
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


def _normalized_entity(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def evidence_belongs_to_case(record: EvidenceRecord, case: InvestigationCase) -> bool:
    """Reject evidence explicitly bound to another case, transaction, or customer."""
    return all(
        (
            not expected
            or not actual
            or str(actual).strip() == str(expected).strip()
        )
        for actual, expected in (
            (record.case_id, case.case_id),
            (record.transaction_id or record.data.get("transaction_id"), case.transaction.transaction_id),
            (record.customer_id or record.data.get("customer_id"), case.transaction.customer_id),
        )
    )


def usable_entity_sanctions_status(
    record: Optional[EvidenceRecord],
    transaction: Transaction,
) -> str:
    """
    Return a sanctions status only when a source record supports the entity claim.

    A jurisdiction, bank location, substring, or missing provider record is not an
    entity-level sanctions match.
    """
    if record is None:
        return "UNKNOWN"
    status = str(record.data.get("match_status", "UNKNOWN")).upper()
    if status == "NO_MATCH":
        return "NO_MATCH"
    if status not in {"CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT"}:
        return "UNKNOWN"

    matched_name = (
        record.data.get("matched_name")
        or record.data.get("matched_entity")
        or record.data.get("counterparty_name")
    )
    matched_account = record.data.get("matched_account") or record.data.get("counterparty_account")
    exact_name = bool(matched_name) and _normalized_entity(matched_name) == _normalized_entity(transaction.counterparty_name)
    exact_account = bool(matched_account) and str(matched_account).strip() == str(transaction.counterparty_account).strip()
    has_list_reference = bool(
        record.data.get("list_id")
        or record.data.get("list_record_id")
        or record.data.get("source_record_id")
        or record.source_version
    )
    has_source = bool(record.source_system and record.evidence_id and record.timestamp)

    if not (has_source and has_list_reference and (exact_name or exact_account)):
        return "UNKNOWN"
    return status

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
        self.quarantined_evidence: List[Dict[str, Any]] = []


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
        recorded_name = sanctions_rec.data.get("counterparty_name")
        if (
            recorded_name
            and _normalized_entity(recorded_name) != _normalized_entity(case.transaction.counterparty_name)
        ):
            conflicts.append({
                "type": "SANCTIONS_ENTITY_MISMATCH",
                "evidence_ids": [sanctions_rec.evidence_id],
                "description": (
                    f"Screening record names '{recorded_name}', not "
                    f"beneficiary '{case.transaction.counterparty_name}'."
                ),
            })
        recorded_account = sanctions_rec.data.get("counterparty_account")
        if recorded_account and recorded_account != case.transaction.counterparty_account:
            conflicts.append({
                "type": "SANCTIONS_ACCOUNT_MISMATCH",
                "evidence_ids": [sanctions_rec.evidence_id],
                "description": "Screening record account does not match the transaction beneficiary account.",
            })
        feed_a = sanctions_rec.data.get("feed_a_status")
        feed_b = sanctions_rec.data.get("feed_b_status")
        if feed_a and feed_b and feed_a != feed_b:
            conflicts.append({
                "type": "SANCTIONS_FEED_CONTRADICTION",
                "evidence_ids": [sanctions_rec.evidence_id],
                "description": f"Sanctions feed A ({feed_a}) directly contradicts feed B ({feed_b})"
            })

    # 5. Contradictory KYC profile records across multiple providers
    kyc_records = [r for r in case.evidence_records if r.evidence_type == "KYC_PROFILE"]
    if len(kyc_records) >= 2:
        statuses = {r.data.get("verification_status") for r in kyc_records if r.data.get("verification_status")}
        has_verified = "VERIFIED" in statuses
        has_failed = any(
            str(s).upper() in ("FAILED", "FAILED_FRAUDULENT_ID", "FRAUDULENT", "REJECTED", "UNVERIFIED")
            for s in statuses
        )
        if has_verified and has_failed:
            conflicts.append({
                "type": "KYC_VERIFICATION_CONTRADICTION",
                "evidence_ids": [r.evidence_id for r in kyc_records],
                "description": f"Conflicting KYC verification statuses across providers: {statuses}"
            })

    # 6. Contradictory Sanctions screening records across multiple feeds
    sanctions_records = [r for r in case.evidence_records if r.evidence_type == "SANCTIONS_PEP_SCREENING"]
    if len(sanctions_records) >= 2:
        m_statuses = {r.data.get("match_status") for r in sanctions_records if r.data.get("match_status")}
        has_hit = any(s in ("CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT") for s in m_statuses)
        has_clear = "NO_MATCH" in m_statuses
        if has_hit and has_clear:
            conflicts.append({
                "type": "SANCTIONS_FEED_CONTRADICTION",
                "evidence_ids": [r.evidence_id for r in sanctions_records],
                "description": f"Conflicting sanctions screening statuses across feeds: {m_statuses}"
            })

    return conflicts


def check_missing_required_evidence(case: InvestigationCase) -> List[str]:
    """Check mandatory evidence types per regulatory risk policy."""
    missing = []
    available_types = {
        r.evidence_type for r in case.evidence_records
        if evidence_belongs_to_case(r, case)
    }

    # Policy: High value wires (>= $10,000) or international wires require KYC and Sanctions screening
    is_high_value = case.transaction.amount >= 10000.0
    is_wire = "WIRE" in case.transaction.channel.upper()

    if is_high_value or is_wire:
        if "KYC_PROFILE" not in available_types:
            missing.append("KYC_PROFILE")
        sanctions_record = next(
            (
                record for record in case.evidence_records
                if record.evidence_type == "SANCTIONS_PEP_SCREENING"
                and evidence_belongs_to_case(record, case)
            ),
            None,
        )
        if (
            sanctions_record is None
            or (
                usable_entity_sanctions_status(sanctions_record, case.transaction) == "UNKNOWN"
                and sanctions_record.data.get("match_status") != "NO_MATCH"
            )
        ):
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
            v_claim.support_status = "unsupported"
            v_claim.review_required = True
            v_claim.validation_notes = "Claim asserts a material outcome without citing evidence IDs."
            validated.append(v_claim)
            continue

        # Check if all cited IDs exist in this exact case
        non_existent_ids = [
            eid for eid in v_claim.evidence_ids
            if eid != tx_id and eid not in evidence_id_map
        ]
        if non_existent_ids:
            v_claim.support_status = "unsupported"
            v_claim.review_required = True
            v_claim.validation_notes = f"Referenced non-existent or foreign evidence IDs: {non_existent_ids}"
            validated.append(v_claim)
            continue

        # 1b. Validate evidence record case and customer binding
        foreign_evidence = False
        foreign_note = ""
        for eid in v_claim.evidence_ids:
            if eid in evidence_id_map:
                rec = evidence_id_map[eid]
                if not evidence_belongs_to_case(rec, case):
                    foreign_evidence = True
                    mismatch_parts = []
                    if rec.case_id and rec.case_id != case.case_id:
                        mismatch_parts.append(f"bound to external case '{rec.case_id}'")
                    if (rec.transaction_id or rec.data.get("transaction_id")) not in (None, tx_id):
                        mismatch_parts.append(
                            f"bound to external transaction '{rec.transaction_id or rec.data.get('transaction_id')}'"
                        )
                    if (rec.customer_id or rec.data.get("customer_id")) not in (
                        None,
                        case.transaction.customer_id,
                    ):
                        mismatch_parts.append(
                            f"bound to external customer '{rec.customer_id or rec.data.get('customer_id')}'"
                        )
                    foreign_note = (
                        f"Evidence ID '{eid}' is not bound to case '{case.case_id}', "
                        f"transaction '{tx_id}', or customer '{case.transaction.customer_id}': "
                        + ", ".join(mismatch_parts)
                    )
                    break
                rec_tx = rec.data.get("transaction_id")
                if rec_tx and rec_tx != tx_id:
                    foreign_evidence = True
                    foreign_note = f"Evidence ID '{eid}' is bound to external transaction '{rec_tx}', not case '{tx_id}'."
                    break
                rec_cust = rec.data.get("customer_id")
                if rec_cust and rec_cust != case.transaction.customer_id:
                    foreign_evidence = True
                    foreign_note = f"Evidence ID '{eid}' is bound to external customer '{rec_cust}', not case customer '{case.transaction.customer_id}'."
                    break
        if foreign_evidence:
            v_claim.support_status = "unsupported"
            v_claim.review_required = True
            v_claim.validation_notes = foreign_note
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

        # 4. Check if claim adopted untrusted prompt injection assertions or uncorroborated cyber claims
        text_lower = v_claim.text.lower()
        if injection_detected:
            if any(term in text_lower for term in [
                "exempt", "board of directors", "executive treaty", "override",
                "disregard", "cleared by admin", "safe to ignore"
            ]):
                v_claim.support_status = "unsupported"
                v_claim.review_required = True
                v_claim.validation_notes = "Claim echoes untrusted injection instruction from input payload."
                validated.append(v_claim)
                continue

        # 4b. Disallow treating unverified memo cybersecurity logs as established financial fraud
        CYBER_ASSERTIONS = ["ssh", "unauthorized login", "failed password", "brute force", "compromised deploy"]
        if any(term in text_lower for term in CYBER_ASSERTIONS):
            # Check if any evidence record actually supports a cybersecurity breach
            has_cyber_evidence = any(
                r.evidence_type in ("DEVICE_IP_TELEMETRY", "ACCOUNT_HISTORY") and
                r.data.get("security_compromise_verified") is True
                for r in case.evidence_records
            )
            if not has_cyber_evidence:
                v_claim.support_status = "unsupported"
                v_claim.review_required = True
                v_claim.validation_notes = (
                    "Claim asserts cybersecurity breach/SSH activity based solely on raw memo text "
                    "without independent corroboration from security telemetry."
                )
                validated.append(v_claim)
                continue

        # 4c. Do not infer criminal activity or illicit conspiracy from an IP proxy indicator alone
        if any(term in text_lower for term in ["criminal", "illicit syndicate", "fraud ring", "money laundering operation"]):
            has_substantive_fraud = any(
                r.data.get("fraud_confirmed") is True or r.data.get("security_compromise_verified") is True
                for r in case.evidence_records
            )
            if not has_substantive_fraud:
                v_claim.support_status = "unsupported"
                v_claim.review_required = True
                v_claim.validation_notes = "Criminal activity cannot be inferred from proxy or metadata indicators alone."
                validated.append(v_claim)
                continue

        # 4d. Semantic verification against actual evidence data
        semantic_issue = False
        semantic_note = ""
        for eid in v_claim.evidence_ids:
            if eid in evidence_id_map:
                rec = evidence_id_map[eid]
                if rec.evidence_type == "SANCTIONS_PEP_SCREENING":
                    m_status = usable_entity_sanctions_status(rec, case.transaction)
                    if "confirmed match" in text_lower and m_status != "CONFIRMED_MATCH":
                        semantic_issue = True
                        semantic_note = f"Claim describes sanctions match as confirmed, but evidence '{eid}' reports '{m_status}'."
                        break
                    if any(term in text_lower for term in ["clean", "cleared", "no match", "not sanctioned"]) and m_status in ("CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT"):
                        semantic_issue = True
                        semantic_note = f"Claim claims sanctions cleared, but evidence '{eid}' shows match '{m_status}'."
                        break
                elif rec.evidence_type == "DEVICE_IP_TELEMETRY":
                    vpn = rec.data.get("vpn_or_proxy_detected", False)
                    if any(term in text_lower for term in ["no proxy", "residential connection", "direct ip"]) and vpn:
                        semantic_issue = True
                        semantic_note = f"Claim asserts direct connection, but evidence '{eid}' detected proxy/VPN."
                        break
                    if any(term in text_lower for term in ["proxy detected", "vpn active"]) and not vpn:
                        semantic_issue = True
                        semantic_note = f"Claim asserts proxy detected, but evidence '{eid}' reports clean IP routing."
                        break
                elif rec.evidence_type == "KYC_PROFILE":
                    v_status = rec.data.get("verification_status", "UNVERIFIED")
                    if any(term in text_lower for term in ["verified kyc", "kyc passed", "kyc complete"]) and v_status != "VERIFIED":
                        semantic_issue = True
                        semantic_note = f"Claim asserts verified KYC, but evidence '{eid}' has status '{v_status}'."
                        break

        if semantic_issue:
            v_claim.support_status = "conflicting"
            v_claim.review_required = True
            v_claim.validation_notes = semantic_note
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
    foreign_records = [
        r.evidence_id for r in case.evidence_records
        if not evidence_belongs_to_case(r, case)
    ]
    if foreign_records:
        report.validation_warnings.append(
            f"Evidence records rejected for case binding mismatch: {foreign_records}"
        )
        report.quarantined_evidence.extend(
            {
                "evidence_id": evidence_id,
                "reason": "CASE_BINDING_MISMATCH",
                "status": "QUARANTINED",
            }
            for evidence_id in foreign_records
        )

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
    evidence_id_set = {
        r.evidence_id for r in case.evidence_records
        if evidence_belongs_to_case(r, case)
    } | {case.transaction.transaction_id}
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
        if c.support_status != "supported":
            report.quarantined_evidence.append(
                {
                    "claim_id": c.claim_id,
                    "evidence_ids": c.evidence_ids,
                    "reason": c.validation_notes or c.support_status,
                    "status": "QUARANTINED",
                }
            )

    return report


def compute_grounding_status(report: ValidationReport, fast_path: bool = False) -> str:
    """
    Substantive grounding status: FULLY_GROUNDED, PARTIALLY_GROUNDED, UNGROUNDED.
    A result with zero quarantined claims is NOT automatically fully grounded.
    """
    if fast_path:
        return "FULLY_GROUNDED"

    if (
        report.untrusted_instruction_detected
        or report.unsupported_claims_count > 0
        or report.conflicting_claims_count > 0
        or (report.total_claims_count == 0)
    ):
        return "UNGROUNDED"

    if (
        report.stale_claims_count > 0
        or report.missing_required_evidence
        or (report.traceable_claims_count < report.total_claims_count)
    ):
        return "PARTIALLY_GROUNDED"

    return "FULLY_GROUNDED"
