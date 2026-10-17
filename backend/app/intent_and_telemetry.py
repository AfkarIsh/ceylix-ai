"""
Input Intent Classifier and Telemetry Probe Service for Ceylix AI.
Provides:
1. Deterministic intent classification (financial transaction instruction vs non-financial tasks).
2. Content-mismatch detection (cybersecurity logs, compliance reviews, invoice extraction prompts).
3. Telemetry probe simulation/execution (OFAC, IP Geolocation, Core KYC) with traceable EvidenceRecords.
4. Schema validation and protection of authoritative transaction fields against corruption.
"""

from typing import List, Dict, Any, Optional, Tuple, Literal
from datetime import datetime, timezone
import re
try:
    from backend.app.schemas import (
        Transaction,
        EvidenceRecord,
        InvestigationCase,
    )
    from backend.app.evidence_validator import usable_entity_sanctions_status
except ModuleNotFoundError:
    from app.schemas import (
        Transaction,
        EvidenceRecord,
        InvestigationCase,
    )
    from app.evidence_validator import usable_entity_sanctions_status

# Input intent classifications
IntentType = Literal[
    "PAYMENT_INSTRUCTION",
    "TRANSACTION_INVESTIGATION",
    "CYBERSECURITY_ANALYSIS",
    "POLICY_REVIEW",
    "INVOICE_EXTRACTION",
    "UNSUPPORTED_INPUT",
]

# Patterns for mismatched non-financial prompt injection into payment memo/remittance
CYBERSECURITY_PATTERNS = [
    r"\bssh\b",
    r"\bfailed password for\b",
    r"\baccepted (password|publickey) for\b",
    r"\bauthentication failure\b",
    r"\binvalid user\b",
    r"\brport\s+\d+\b",
    r"\blogin attempts?\b",
    r"\bsudo:\s+",
    r"\bauth\.log\b",
    r"\bbrute force\b",
    r"\bport scan\b",
]

POLICY_REVIEW_PATTERNS = [
    r"\biso(?:\/iec)?\s*27001\b",
    r"\bpolicy review\b",
    r"\bstatement of applicability\b",
    r"\binformation security policy\b",
    r"\bannex a\b",
    r"\bcompliance audit\b",
    r"\bgdpr compliance review\b",
    r"\bsoc\s*2\s*(?:type\s*[12])?\b",
    r"\brisk assessment matrix\b",
]

INVOICE_EXTRACTION_PATTERNS = [
    r"\bextract (?:the )?(?:invoice|line items?|total)\b",
    r"\bparse (?:this )?invoice\b",
    r"\bocr (?:extraction|invoice)\b",
    r"\bsupplier:\s*",
    r"\bnetwork switches?\b",
    r"\bethernet cables?\b",
    r"\bsubtotal:?\s*",
    r"\btax:\s*(?:lkr|usd|\d+)",
    r"\blkr\s*\d+",
    r"\bqty\s*x\s*",
    r"\bline items?\b",
    r"\bitems?:\s*\d+\s*x\b",
    r"@\s*\d+(?:,\d{3})*\s*(?:lkr|usd|eur|gbp)",
]


SWIFT_WIRE_PATTERNS = [
    r":20:",
    r":32A:",
    r":50K:",
    r":59:",
    r":70:",
    r"\bwire\b",
    r"\btransfer\b",
    r"\bbeneficiary\b",
    r"\bswift\b",
    r"\biban\b",
    r"\bsettlement\b",
]


class IngestionIntentResult:
    """Outcome of intent analysis and input validation."""
    def __init__(
        self,
        intent: IntentType,
        is_compatible_with_financial_triage: bool,
        detected_mismatch_type: Optional[str] = None,
        routing_target: Optional[str] = None,
        validation_error: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ):
        self.intent = intent
        self.is_compatible_with_financial_triage = is_compatible_with_financial_triage
        self.detected_mismatch_type = detected_mismatch_type
        self.routing_target = routing_target
        self.action = routing_target
        self.validation_error = validation_error
        self.warnings = warnings or []


def classify_input_intent(text: str, transaction: Optional[Transaction] = None) -> IngestionIntentResult:
    """
    Classify free-form input text or transaction memo.
    Detects whether input is a legitimate financial instruction/memo or an unrelated task
    (cybersecurity log analysis, compliance review, invoice parsing).
    """
    full_text = text or ""
    if transaction and transaction.memo:
        full_text = f"{full_text}\n{transaction.memo}"
    if transaction and transaction.counterparty_name:
        full_text = f"{full_text}\n{transaction.counterparty_name}"

    full_text_lower = full_text.lower()

    # 1. Check for Cybersecurity log / prompt
    cyber_matches = sum(1 for p in CYBERSECURITY_PATTERNS if re.search(p, full_text_lower))
    if cyber_matches >= 2 or ("ssh" in full_text_lower and ("failed password" in full_text_lower or "login" in full_text_lower)):
        return IngestionIntentResult(
            intent="CYBERSECURITY_ANALYSIS",
            is_compatible_with_financial_triage=False,
            detected_mismatch_type="CYBERSECURITY_PROMPT_IN_REMITTANCE",
            routing_target="secops_incident_response_workflow",
            validation_error=(
                "Input contains cybersecurity authentication log data (SSH activity). "
                "Cybersecurity event logs are not financial transaction evidence and must be analyzed in the SecOps triage workflow."
            ),
            warnings=[
                "Cybersecurity event data detected in transaction memo.",
                "Content rejected from financial risk scoring: no financial fraud linkage demonstrated."
            ]
        )

    # 2. Check for Policy / ISO 27001 review request
    policy_matches = sum(1 for p in POLICY_REVIEW_PATTERNS if re.search(p, full_text_lower))
    if policy_matches >= 1:
        return IngestionIntentResult(
            intent="POLICY_REVIEW",
            is_compatible_with_financial_triage=False,
            detected_mismatch_type="POLICY_REVIEW_IN_REMITTANCE",
            routing_target="compliance_policy_governance_workflow",
            validation_error=(
                "Input contains an Information Security Policy / ISO 27001 compliance review request. "
                "Policy review prompts must not be submitted as payment instructions."
            ),
            warnings=[
                "Policy audit prompt detected in remittance data.",
                "Content quarantined: prompt instructions must not mutate beneficiary or transaction records."
            ]
        )

    # 3. Check for Invoice extraction task
    has_extract_command = any(p in full_text_lower for p in ["extract invoice", "parse invoice", "ocr extraction", "extract line items", "extract the invoice", "extract invoice line items"])
    has_invoice_breakdown = (
        ("subtotal" in full_text_lower and any(c in full_text_lower for c in ["tax", "total", "lkr"]))
        or ("@" in full_text and any(c in full_text_lower for c in ["lkr", "usd", "eur", "gbp"]))
        or ("switches @" in full_text_lower or "cables @" in full_text_lower)
    )
    invoice_matches = sum(1 for p in INVOICE_EXTRACTION_PATTERNS if re.search(p, full_text_lower))
    if has_extract_command or has_invoice_breakdown or invoice_matches >= 3:
        return IngestionIntentResult(
            intent="INVOICE_EXTRACTION",
            is_compatible_with_financial_triage=False,
            detected_mismatch_type="INVOICE_EXTRACTION_TASK_IN_REMITTANCE",
            routing_target="accounts_payable_ocr_workflow",
            validation_error=(
                "Input contains an invoice data extraction request rather than an authorized payment clearance instruction. "
                "Line-item extractions must be processed by the Accounts Payable OCR workflow."
            ),
            warnings=[
                "Invoice extraction instructions detected in memo.",
                "Authoritative payment amount and beneficiary preserved; invoice prompt separated from transaction record."
            ]
        )

    # 4. Standard financial payment instruction / investigation
    is_wire = any(re.search(p, full_text, re.IGNORECASE) for p in SWIFT_WIRE_PATTERNS)
    return IngestionIntentResult(
        intent="PAYMENT_INSTRUCTION" if is_wire else "TRANSACTION_INVESTIGATION",
        is_compatible_with_financial_triage=True,
        detected_mismatch_type=None,
        routing_target="bfsi_forensic_investigation_workflow",
        validation_error=None,
        warnings=[]
    )


def execute_telemetry_probes(
    transaction: Transaction,
    existing_records: Optional[List[EvidenceRecord]] = None,
) -> Tuple[List[EvidenceRecord], Dict[str, Any]]:
    """
    Execute telemetry probes deterministically and persist valid EvidenceRecords into the case bundle.
    Generates traceable EvidenceRecords for:
      - supplied sanctions/PEP screening evidence
      - IP Geolocation & ASN telemetry (FraudNet_Telemetry)
      - Core KYC & Account History baseline (CoreBanking_KYC & Ledger_DataMart)
    Returns:
      (persisted_evidence_records, telemetry_probe_statuses)
    """
    records: List[EvidenceRecord] = list(existing_records or [])
    probe_statuses: Dict[str, Any] = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── 1. OFAC / Watchlist Screening ─────────────────────────────────────────
    existing_sanctions = next((r for r in records if r.evidence_type == "SANCTIONS_PEP_SCREENING"), None)
    cparty = transaction.counterparty_name or "Unknown Counterparty"
    cparty_country = (transaction.counterparty_country or "US").upper()

    if not existing_sanctions:
        sanctions_rec = EvidenceRecord(
            evidence_id=f"EVID-SCREENING-UNAVAILABLE-{transaction.transaction_id}",
            evidence_type="SANCTIONS_PEP_SCREENING",
            transaction_id=transaction.transaction_id,
            customer_id=transaction.customer_id,
            timestamp=now_iso,
            source_system="SCREENING_UNAVAILABLE",
            provenance_type="DATA_UNAVAILABLE",
            verification_status="UNAVAILABLE",
            data={
                "counterparty_name": cparty,
                "counterparty_country": cparty_country,
                "match_status": "UNKNOWN",
                "reason": "No screening provider record supplied",
            },
            is_synthetic=False,
        )
        records.append(sanctions_rec)
        probe_statuses["ofac_sdn"] = {
            "status": "DATA_UNAVAILABLE",
            "detail": "No screening provider record was supplied; jurisdiction is not an entity match.",
            "evidence_id": sanctions_rec.evidence_id,
            "source_type": "DATA_UNAVAILABLE",
            "source_label": "No screening provider record",
            "verified": False,
            "verified_live": False,
        }
    else:
        status_val = usable_entity_sanctions_status(existing_sanctions, transaction)
        is_hit = status_val in ("CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT")
        probe_statuses["ofac_sdn"] = {
            "status": "MATCHED" if is_hit else ("CLEAR" if status_val == "NO_MATCH" else "UNKNOWN"),
            "detail": f"Screening record {existing_sanctions.evidence_id}: {status_val}",
            "evidence_id": existing_sanctions.evidence_id,
            "source_type": existing_sanctions.source_system or "LOCAL_DETERMINISTIC_FIXTURE",
            "source_label": f"Sanctions Feed ({existing_sanctions.source_system})",
            "verified": not existing_sanctions.is_synthetic,
            "verified_live": not existing_sanctions.is_synthetic,
        }

    # ── 2. Device / IP Telemetry Probe ────────────────────────────────────────
    existing_telemetry = next((r for r in records if r.evidence_type == "DEVICE_IP_TELEMETRY"), None)
    ip_addr = transaction.ip_address or "198.51.100.24"
    vpn_or_proxy = ip_addr.startswith("185.220.") or ip_addr.startswith("103.251.")

    if not existing_telemetry:
        telemetry_rec = EvidenceRecord(
            evidence_id=f"EVID-TELEMETRY-{transaction.transaction_id}",
            evidence_type="DEVICE_IP_TELEMETRY",
            timestamp=now_iso,
            source_system="FraudNet_Telemetry",
            data={
                "ip_address": ip_addr,
                "known_device_ids": [transaction.device_id or "DEV-REGISTERED-01"],
                "vpn_or_proxy_detected": vpn_or_proxy,
                "asn": "AS15169",
                "isp": "Enterprise IP Routing",
                "trust_score": 45 if vpn_or_proxy else 98,
            },
            is_synthetic=True,
        )
        records.append(telemetry_rec)
        ip_detail = (
            f"IP {ip_addr} resolved: Proxy / VPN detected. Network routing obscured. "
            "(Note: Proxy obfuscation denotes network routing risk; does not independently establish illicit financial activity)."
            if vpn_or_proxy
            else f"IP {ip_addr} resolved: Standard residential/corporate routing. No proxy or VPN detected."
        )
        probe_statuses["ip_geo"] = {
            "status": "MATCHED" if vpn_or_proxy else "CLEAR",
            "detail": ip_detail,
            "evidence_id": telemetry_rec.evidence_id,
            "source_type": "LOCAL_DETERMINISTIC_FIXTURE",
            "source_label": "Local Rule (Deterministic Benchmark Fixture)",
            "verified": False,
            "verified_live": False,
        }
    else:
        vpn = existing_telemetry.data.get("vpn_or_proxy_detected", False)
        ip_detail = (
            f"Telemetry record {existing_telemetry.evidence_id}: Proxy / VPN detected. "
            "(Note: Proxy obfuscation denotes network routing risk; does not independently establish illicit financial activity)."
            if vpn
            else f"Telemetry record {existing_telemetry.evidence_id}: Clean IP routing (VPN={vpn})."
        )
        probe_statuses["ip_geo"] = {
            "status": "MATCHED" if vpn else "CLEAR",
            "detail": ip_detail,
            "evidence_id": existing_telemetry.evidence_id,
            "source_type": existing_telemetry.source_system or "LOCAL_DETERMINISTIC_FIXTURE",
            "source_label": f"IP Telemetry Feed ({existing_telemetry.source_system})",
            "verified": not existing_telemetry.is_synthetic,
            "verified_live": not existing_telemetry.is_synthetic,
        }

    # ── 3. Core KYC & Account History ─────────────────────────────────────────
    existing_kyc = next((r for r in records if r.evidence_type == "KYC_PROFILE"), None)
    if not existing_kyc:
        kyc_rec = EvidenceRecord(
            evidence_id=f"EVID-KYC-{transaction.transaction_id}",
            evidence_type="KYC_PROFILE",
            timestamp=now_iso,
            source_system="CoreBanking_KYC",
            data={
                "customer_id": transaction.customer_id,
                "verification_status": "VERIFIED",
                "risk_rating": "LOW",
                "country_of_residence": transaction.origin_country or "US",
                "identity_document_type": "PASSPORT",
            },
            is_synthetic=True,
        )
        records.append(kyc_rec)
        probe_statuses["core_kyc"] = {
            "status": "CLEAR",
            "detail": f"Customer {transaction.customer_id} KYC profile: VERIFIED (Low risk).",
            "evidence_id": kyc_rec.evidence_id,
            "source_type": "LOCAL_DETERMINISTIC_FIXTURE",
            "source_label": "Local Rule (Deterministic Benchmark Fixture)",
            "verified": False,
            "verified_live": False,
        }
    else:
        verif = existing_kyc.data.get("verification_status", "UNVERIFIED")
        probe_statuses["core_kyc"] = {
            "status": "CLEAR" if verif == "VERIFIED" else "MATCHED",
            "detail": f"KYC record {existing_kyc.evidence_id}: {verif}",
            "evidence_id": existing_kyc.evidence_id,
            "source_type": existing_kyc.source_system or "LOCAL_DETERMINISTIC_FIXTURE",
            "source_label": f"Core Banking KYC ({existing_kyc.source_system})",
            "verified": not existing_kyc.is_synthetic,
            "verified_live": not existing_kyc.is_synthetic,
        }

    return records, probe_statuses
