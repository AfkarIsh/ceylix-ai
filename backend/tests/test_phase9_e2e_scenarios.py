"""
Phase 9 — Required End-to-End Regression Test Suite (Scenarios A through P).
Verifies the complete Ceylix AI platform architecture across all mandated scenarios:
A. Benign domestic grocery payment
B. High-risk corridor and unrelated SSH memo
C. ISO policy-review memo
D. Invoice-extraction memo
E. Valid sanctions match
F. Nonmatching beneficiary
G. Missing/unavailable sanctions and KYC
H. Proxy/VPN detection
I. High-value transaction
J. Structuring and velocity
K. Cross-case evidence
L. Repeated submission
M. Contradictory evidence
N. Novel suspicious pattern
O. Provider failure
P. Frontend/API consistency
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from backend.app.schemas import (
    InvestigationCase,
    Transaction,
    EvidenceRecord,
    Claim,
    InvestigationReport,
)
from backend.app.workflows import (
    run_validated_workflow,
    run_baseline_workflow,
)
from backend.app.intent_and_telemetry import (
    classify_input_intent,
    execute_telemetry_probes,
)
from backend.app.rules import (
    run_all_deterministic_rules,
    build_risk_dimension_breakdown,
)
from backend.app.evidence_validator import (
    perform_deterministic_validation,
    compute_grounding_status,
)
from backend.app.anomaly_detector import (
    detect_transaction_anomalies,
)


# =============================================================================
# SCENARIO A: Benign domestic grocery payment
# =============================================================================
def test_scenario_a_benign_domestic_grocery():
    """Scenario A: Low amount domestic retail payment clears via System-1 fast-path."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-A",
        category="benign_and_suspicious_controls",
        scenario_name="Benign Domestic Grocery",
        transaction=Transaction(
            transaction_id="TX-A-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-A-01",
            customer_id="CUST-A-01",
            amount=85.50,
            currency="USD",
            channel="POS_CHIP",
            counterparty_account="ACC-GROCERY-01",
            counterparty_name="WHOLE FOODS MARKET",
            counterparty_bank="JPMorgan Chase",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
            memo="Weekly grocery supplies",
        ),
        evidence_records=[],
    )
    report = run_validated_workflow(case)
    assert report.fast_path_used is True
    assert report.preliminary_risk_level == "LOW"
    assert report.decision == "RELEASE_WITH_PROVENANCE"
    assert report.sar_recommendation is False
    assert report.sar_rationale is None
    assert report.grounding_status == "FULLY_GROUNDED"
    assert report.risk_dimensions is not None
    assert report.risk_dimensions.financial_transaction_risk["status"] == "CLEAR"


# =============================================================================
# SCENARIO B: High-risk corridor and unrelated SSH memo
# =============================================================================
def test_scenario_b_high_risk_corridor_with_ssh_memo():
    """Scenario B: Unrelated SSH memo does not suppress genuine sanctions risk."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-B",
        category="benign_and_suspicious_controls",
        scenario_name="High-Risk Corridor SSH Memo",
        transaction=Transaction(
            transaction_id="TX-B-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-B-01",
            customer_id="CUST-B-01",
            amount=142.50,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-IRAN-01",
            counterparty_name="GLOBAL HORIZON HOLDINGS",
            counterparty_bank="Bank Melli Iran",
            counterparty_country="IR",
            origin_country="US",
            destination_country="IR",
            memo="Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",
        ),
        evidence_records=[],
    )
    report = run_validated_workflow(case)
    # Original structured transaction facts preserved
    assert case.transaction.counterparty_country == "IR"
    assert case.transaction.counterparty_name == "GLOBAL HORIZON HOLDINGS"
    assert case.transaction.amount == 142.50
    # Independent financial risk evaluation
    assert report.preliminary_risk_level == "HIGH"
    assert report.input_intent == "CYBERSECURITY_ANALYSIS"
    assert report.decision == "ABSTAIN_FOR_HUMAN_REVIEW"
    assert any("SANCTIONS_OR_JURISDICTION_HOLD" in r for r in report.abstention_reasons)
    assert report.sar_recommendation is False
    assert report.sar_rationale is None


# =============================================================================
# SCENARIO C: ISO policy-review memo
# =============================================================================
def test_scenario_c_iso_policy_review_memo():
    """Scenario C: ISO policy memo detects intent and does not mutate transaction facts."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-C",
        category="untrusted_instructions",
        scenario_name="ISO 27001 Review Memo",
        transaction=Transaction(
            transaction_id="TX-C-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-C-01",
            customer_id="CUST-C-01",
            amount=250.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-C-02",
            counterparty_name="Northwest Consulting LLC",
            counterparty_bank="Bank of America, N.A.",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
            memo="Please review Information Security Policy according to ISO/IEC 27001:2022 clause A.5.15 access control.",
        ),
        evidence_records=[],
    )
    report = run_validated_workflow(case)
    assert report.input_intent == "POLICY_REVIEW"
    assert case.transaction.counterparty_name == "Northwest Consulting LLC"
    assert report.preliminary_risk_level == "LOW"
    assert report.sar_recommendation is False
    assert report.decision == "ABSTAIN_FOR_HUMAN_REVIEW"


# =============================================================================
# SCENARIO D: Invoice-extraction memo
# =============================================================================
def test_scenario_d_invoice_extraction_memo():
    """Scenario D: Invoice amounts and currencies in memo do not overwrite structured facts."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-D",
        category="untrusted_instructions",
        scenario_name="Invoice Extraction Memo",
        transaction=Transaction(
            transaction_id="TX-D-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-D-01",
            customer_id="CUST-D-01",
            amount=50000.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-D-02",
            counterparty_name="Lanka Tech Supplies",
            counterparty_bank="Bank of America, N.A.",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
            memo="Invoice INV-9901: 2 switches @ 45,000 LKR each. Total: 90,000 LKR.",
        ),
        evidence_records=[],
    )
    res = classify_input_intent(case.transaction.memo, case.transaction)
    assert res.intent == "INVOICE_EXTRACTION"
    # Currency and amount intact
    assert case.transaction.amount == 50000.00
    assert case.transaction.currency == "USD"
    assert case.transaction.counterparty_name == "Lanka Tech Supplies"


# =============================================================================
# SCENARIO E: Valid sanctions match
# =============================================================================
def test_scenario_e_valid_sanctions_match():
    """Scenario E: Entity-level sanctions match triggers mandatory hold and SAR."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-E",
        category="complete_consistent",
        scenario_name="Validated Sanctions Hit",
        transaction=Transaction(
            transaction_id="TX-E-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-E-01",
            customer_id="CUST-E-01",
            amount=7500.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-SANCTIONED-01",
            counterparty_name="KORYO TRADING CO",
            counterparty_bank="Foreign Trade Bank",
            counterparty_country="KP",
            origin_country="US",
            destination_country="KP",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-E-SANC-01",
                evidence_type="SANCTIONS_PEP_SCREENING",
                case_id="CASE-SCENARIO-E",
                transaction_id="TX-E-001",
                customer_id="CUST-E-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="OFAC_SDN_FIXTURE",
                data={
                    "counterparty_name": "KORYO TRADING CO",
                    "match_status": "CONFIRMED_MATCH",
                    "list_id": "OFAC-SDN-1029",
                },
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="MATCHED",
            )
        ],
    )
    rules = run_all_deterministic_rules(case)
    sanc_rule = next(r for r in rules if r.rule_name == "SanctionsWatchlistRule")
    assert sanc_rule.flagged is True
    assert sanc_rule.severity == "HIGH"

    claims = [
        Claim(
            claim_id="CLM-E-1",
            text="Beneficiary KORYO TRADING CO confirmed on OFAC SDN list.",
            claim_type="factual_assertion",
            evidence_ids=["EV-E-SANC-01"],
            support_status="supported",
        )
    ]
    val = perform_deterministic_validation(case, claims)
    assert val.validated_claims[0].support_status == "supported"


# =============================================================================
# SCENARIO F: Nonmatching beneficiary
# =============================================================================
def test_scenario_f_nonmatching_beneficiary():
    """Scenario F: Do not create a sanctions match without entity-level evidence."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-F",
        category="complete_consistent",
        scenario_name="Nonmatching Beneficiary",
        transaction=Transaction(
            transaction_id="TX-F-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-F-01",
            customer_id="CUST-F-01",
            amount=1500.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-F-02",
            counterparty_name="Smith Clean Logistics Inc",
            counterparty_bank="Chase Bank",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-F-SANC-01",
                evidence_type="SANCTIONS_PEP_SCREENING",
                case_id="CASE-SCENARIO-F",
                transaction_id="TX-F-001",
                customer_id="CUST-F-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="OFAC_SDN_FIXTURE",
                data={"match_status": "NO_MATCH"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="CLEAR",
            )
        ],
    )
    rules = run_all_deterministic_rules(case)
    sanc_rule = next(r for r in rules if r.rule_name == "SanctionsWatchlistRule")
    assert sanc_rule.flagged is False
    assert sanc_rule.passed is True

    # If an unsupported claim attempts to declare a sanctions hit, validator must reject it as conflicting
    false_claim = [
        Claim(
            claim_id="CLM-F-BAD",
            text="Beneficiary has confirmed match on sanctions watchlist.",
            claim_type="factual_assertion",
            evidence_ids=["EV-F-SANC-01"],
            support_status="supported",
        )
    ]
    val = perform_deterministic_validation(case, false_claim)
    assert val.validated_claims[0].support_status == "conflicting"
    assert val.conflicting_claims_count == 1


# =============================================================================
# SCENARIO G: Missing/unavailable sanctions and KYC
# =============================================================================
def test_scenario_g_missing_or_unavailable_feeds():
    """Scenario G: Missing KYC/sanctions evidence returns INFO, not fabricated CLEAR or fraud."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-G",
        category="missing_evidence",
        scenario_name="Missing KYC and Sanctions Feeds",
        transaction=Transaction(
            transaction_id="TX-G-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-G-01",
            customer_id="CUST-G-01",
            amount=400.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-G-02",
            counterparty_name="Apex Parts",
            counterparty_bank="Bank of America",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
        ),
        evidence_records=[],
    )
    rules = run_all_deterministic_rules(case)
    kyc_rule = next(r for r in rules if r.rule_name == "KycVerificationRule")
    sanc_rule = next(r for r in rules if r.rule_name == "SanctionsWatchlistRule")
    assert kyc_rule.severity == "INFO"
    assert kyc_rule.flagged is False
    assert sanc_rule.severity == "INFO"
    assert sanc_rule.flagged is False


# =============================================================================
# SCENARIO H: Proxy/VPN detection
# =============================================================================
def test_scenario_h_proxy_vpn_detection_consistency():
    """Scenario H: Proxy detected IP flags network risk but does not establish financial crime alone."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-H",
        category="benign_and_suspicious_controls",
        scenario_name="Proxy Detected Benign Wire",
        transaction=Transaction(
            transaction_id="TX-H-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-H-01",
            customer_id="CUST-H-01",
            amount=320.00,
            currency="USD",
            channel="ONLINE_BANKING",
            counterparty_account="ACC-H-02",
            counterparty_name="Office Essentials LLC",
            counterparty_bank="Chase Bank",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
            ip_address="185.220.101.12",  # Tor / VPN proxy range
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-H-IP-01",
                evidence_type="DEVICE_IP_TELEMETRY",
                case_id="CASE-SCENARIO-H",
                transaction_id="TX-H-001",
                customer_id="CUST-H-01",
                timestamp="2026-03-30T10:00:00Z",
                source_system="IP_TELEMETRY_FIXTURE",
                data={"vpn_or_proxy_detected": True, "ip": "185.220.101.12"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="MATCHED",
            )
        ],
    )
    rules = run_all_deterministic_rules(case)
    dev_rule = next(r for r in rules if r.rule_name == "DeviceAnomalyRule")
    assert dev_rule.flagged is True
    assert dev_rule.severity == "MEDIUM"  # Not HIGH

    # Proxy alone does not trigger a SAR recommendation
    is_sanctions_hit = any(r.flagged and "Sanctions" in r.rule_name for r in rules)
    is_structuring = any(r.flagged and "Structuring" in r.rule_name for r in rules)
    sar_rec = is_sanctions_hit or is_structuring
    assert sar_rec is False


# =============================================================================
# SCENARIO I: High-value transaction (CTR threshold vs Fraud)
# =============================================================================
def test_scenario_i_high_value_transaction_ctr_handling():
    """Scenario I: High amount ($50,000) with clean KYC/sanctions is RELEASE_QUALIFIED, not fraud."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-I",
        category="complete_consistent",
        scenario_name="High Value Clean Wire",
        transaction=Transaction(
            transaction_id="TX-I-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-I-01",
            customer_id="CUST-I-01",
            amount=50000.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-I-02",
            counterparty_name="Apex Heavy Machinery Corp",
            counterparty_bank="Bank of America, N.A.",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-I-KYC-01",
                evidence_type="KYC_PROFILE",
                case_id="CASE-SCENARIO-I",
                transaction_id="TX-I-001",
                customer_id="CUST-I-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="CoreBanking_KYC",
                data={"verification_status": "VERIFIED"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="VERIFIED",
            ),
            EvidenceRecord(
                evidence_id="EV-I-SANC-01",
                evidence_type="SANCTIONS_PEP_SCREENING",
                case_id="CASE-SCENARIO-I",
                transaction_id="TX-I-001",
                customer_id="CUST-I-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="OFAC_SDN_FIXTURE",
                data={"match_status": "NO_MATCH"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="CLEAR",
            ),
        ],
    )
    rules = run_all_deterministic_rules(case)
    large_rule = next(r for r in rules if r.rule_name == "LargeAmountThresholdRule")
    assert large_rule.flagged is True

    # Validate review policy: Release qualified with advisory notice, no abstention or auto-SAR
    claims = [
        Claim(
            claim_id="CLM-I-1",
            text="Transaction amount $50,000 exceeds CTR reporting baseline.",
            claim_type="factual_assertion",
            evidence_ids=["TX-I-001"],
            support_status="supported",
        )
    ]
    val_report = perform_deterministic_validation(case, claims)
    from backend.app.review_policy import evaluate_review_policy
    decision, abstain, abstention_reasons, warnings = evaluate_review_policy(
        validation_report=val_report,
        rule_results=rules,
        preliminary_risk="LOW",
    )
    assert decision == "RELEASE_QUALIFIED"
    assert abstain is False
    assert any("LargeAmountThresholdRule" in w for w in warnings)


# =============================================================================
# SCENARIO J: Structuring and velocity
# =============================================================================
def test_scenario_j_structuring_and_velocity():
    """Scenario J: Structuring just below CTR threshold ($9,500) and 6x velocity triggers rule."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-J",
        category="benign_and_suspicious_controls",
        scenario_name="Structuring and Velocity Anomaly",
        transaction=Transaction(
            transaction_id="TX-J-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-J-01",
            customer_id="CUST-J-01",
            amount=9500.00,  # Smurfing range: [9000, 9999.99]
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-J-02",
            counterparty_name="Fast Cash Exchange",
            counterparty_bank="Chase Bank",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-J-HIST-01",
                evidence_type="ACCOUNT_HISTORY",
                case_id="CASE-SCENARIO-J",
                transaction_id="TX-J-001",
                customer_id="CUST-J-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="CoreBanking_History",
                data={"avg_30d_transaction_amount": 1200.00},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="VERIFIED",
            )
        ],
    )
    rules = run_all_deterministic_rules(case)
    struct_rule = next(r for r in rules if r.rule_name == "StructuringSmurfingRule")
    vel_rule = next(r for r in rules if r.rule_name == "VelocityAnomalyRule")
    assert struct_rule.flagged is True
    assert vel_rule.flagged is True


# =============================================================================
# SCENARIO K: Cross-case evidence
# =============================================================================
def test_scenario_k_cross_case_evidence_quarantine():
    """Scenario K: Evidence belonging to a foreign case or customer is quarantined."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-K",
        category="benign_and_suspicious_controls",
        scenario_name="Cross Case Injection Test",
        transaction=Transaction(
            transaction_id="TX-K-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-K-01",
            customer_id="CUST-LOCAL-K",
            amount=300.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-K-02",
            counterparty_name="Vendor K",
            counterparty_bank="Bank K",
            counterparty_country="US",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-K-FOREIGN-01",
                evidence_type="KYC_PROFILE",
                case_id="CASE-OTHER-999",  # Foreign case!
                transaction_id="TX-OTHER-999",
                customer_id="CUST-FOREIGN-999",
                timestamp="2026-03-30T10:00:00Z",
                source_system="CoreBanking_KYC",
                data={"customer_id": "CUST-FOREIGN-999", "verification_status": "VERIFIED"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="VERIFIED",
            )
        ],
    )
    claims = [
        Claim(
            claim_id="CLM-K-1",
            text="Customer verified via external KYC record",
            claim_type="factual_assertion",
            evidence_ids=["EV-K-FOREIGN-01"],
            support_status="supported",
        )
    ]
    val = perform_deterministic_validation(case, claims)
    assert val.validated_claims[0].support_status == "unsupported"
    assert "not bound to case" in val.validated_claims[0].validation_notes


# =============================================================================
# SCENARIO L: Repeated submission
# =============================================================================
def test_scenario_l_repeated_submission_idempotency():
    """Scenario L: Repeated executions over identical transaction payload produce identical deterministic results."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-L",
        category="benign_and_suspicious_controls",
        scenario_name="Idempotency Test",
        transaction=Transaction(
            transaction_id="TX-L-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-L-01",
            customer_id="CUST-L-01",
            amount=150.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-L-02",
            counterparty_name="Clean Merchant LLC",
            counterparty_bank="Bank L",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
        ),
        evidence_records=[],
    )
    res_1 = run_all_deterministic_rules(case)
    res_2 = run_all_deterministic_rules(case)
    assert len(res_1) == len(res_2)
    for r1, r2 in zip(res_1, res_2):
        assert r1.rule_name == r2.rule_name
        assert r1.passed == r2.passed
        assert r1.flagged == r2.flagged
        assert r1.severity == r2.severity


# =============================================================================
# SCENARIO M: Contradictory evidence
# =============================================================================
def test_scenario_m_contradictory_evidence_handling():
    """Scenario M: Contradictory evidence triggers UNGROUNDED status and abstention."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-M",
        category="conflicting_evidence",
        scenario_name="Contradictory Evidence Test",
        transaction=Transaction(
            transaction_id="TX-M-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-M-01",
            customer_id="CUST-M-01",
            amount=600.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-M-02",
            counterparty_name="Merchant M",
            counterparty_bank="Bank M",
            counterparty_country="US",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-M-KYC-01",
                evidence_type="KYC_PROFILE",
                case_id="CASE-SCENARIO-M",
                transaction_id="TX-M-001",
                customer_id="CUST-M-01",
                timestamp="2026-03-30T10:00:00Z",
                source_system="CoreBanking_KYC",
                data={"verification_status": "VERIFIED"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="VERIFIED",
            ),
            EvidenceRecord(
                evidence_id="EV-M-KYC-02",
                evidence_type="KYC_PROFILE",
                case_id="CASE-SCENARIO-M",
                transaction_id="TX-M-001",
                customer_id="CUST-M-01",
                timestamp="2026-03-30T10:00:00Z",
                source_system="Experian_KYC",
                data={"verification_status": "FAILED_FRAUDULENT_ID"},
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="UNVERIFIED",
            ),
        ],
    )
    val = perform_deterministic_validation(case, [])
    assert len(val.detected_conflicts) > 0
    grounding = compute_grounding_status(val)
    assert grounding == "UNGROUNDED"


# =============================================================================
# SCENARIO N: Novel suspicious pattern
# =============================================================================
def test_scenario_n_novel_suspicious_pattern():
    """Scenario N: Held-out novel pattern flagged by multivariate anomaly detector without altering deterministic rules."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-N",
        category="benign_and_suspicious_controls",
        scenario_name="Novel Pattern Anomaly",
        transaction=Transaction(
            transaction_id="TX-N-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-N-01",
            customer_id="CUST-N-01",
            amount=8800.00,  # Below $10k CTR, not structuring upper bound
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-N-99",
            counterparty_name="Brand New Unseen Offshore Entity",
            counterparty_bank="Foreign Bank",
            counterparty_country="PA",  # Panama
            origin_country="US",
            destination_country="PA",
            ip_address="185.220.101.12",  # Tor Proxy
            device_id="DEV-UNSEEN-99",
        ),
        evidence_records=[
            EvidenceRecord(
                evidence_id="EV-N-HIST-01",
                evidence_type="ACCOUNT_HISTORY",
                case_id="CASE-SCENARIO-N",
                transaction_id="TX-N-001",
                customer_id="CUST-N-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="CoreBanking_History",
                data={
                    "avg_30d_transaction_amount": 800.00,
                    "std_dev_30d_amount": 250.00,
                    "frequent_counterparties": ["Local Utility Corp", "Landlord Inc"],
                },
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="VERIFIED",
            ),
            EvidenceRecord(
                evidence_id="EV-N-TEL-01",
                evidence_type="DEVICE_IP_TELEMETRY",
                case_id="CASE-SCENARIO-N",
                transaction_id="TX-N-001",
                customer_id="CUST-N-01",
                timestamp="2026-03-30T09:00:00Z",
                source_system="IP_TELEMETRY_FIXTURE",
                data={
                    "vpn_or_proxy_detected": True,
                    "known_device_ids": ["DEV-TRUSTED-01"],
                },
                provenance_type="LOCAL_DETERMINISTIC_FIXTURE",
                verification_status="MATCHED",
            ),
        ],
    )
    anomaly_res = detect_transaction_anomalies(case)
    assert anomaly_res.is_anomaly is True
    assert anomaly_res.anomaly_score >= 0.65
    assert "Statistical novelty flagged" in anomaly_res.explanation
    # Verify deterministic rules did not conflate statistical novelty with confirmed fraud
    rules = run_all_deterministic_rules(case)
    assert all(r.rule_name != "ConfirmedFraudRule" for r in rules)


# =============================================================================
# SCENARIO O: Provider failure handling
# =============================================================================
def test_scenario_o_provider_failure_handling():
    """Scenario O: Provider failure or missing key raises explicit error rather than silently faking CLEAR."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-O",
        category="benign_and_suspicious_controls",
        scenario_name="Provider Failure Test",
        transaction=Transaction(
            transaction_id="TX-O-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-O-01",
            customer_id="CUST-O-01",
            amount=1500.00,
            currency="USD",
            channel="WIRE",
            counterparty_account="ACC-O-02",
            counterparty_name="Vendor O",
            counterparty_bank="Bank O",
            counterparty_country="US",
        ),
        evidence_records=[],
    )
    # When keys are missing or invalid and not fast-path
    from backend.app.gemini_service import call_gemini_api
    with patch("backend.app.gemini_service.GEMINI_API_KEY", ""):
        with patch("backend.app.gemini_service.OPENROUTER_API_KEY", ""):
            with pytest.raises(ValueError) as excinfo:
                call_gemini_api(case)
            assert "No valid Gemini API key configured" in str(excinfo.value)


# =============================================================================
# SCENARIO P: Frontend/API consistency
# =============================================================================
def test_scenario_p_frontend_api_consistency():
    """Scenario P: Authoritative API report provides consistent fields for UI panels."""
    case = InvestigationCase(
        case_id="CASE-SCENARIO-P",
        category="benign_and_suspicious_controls",
        scenario_name="UI Consistency Verification",
        transaction=Transaction(
            transaction_id="TX-P-001",
            timestamp="2026-03-30T10:00:00Z",
            account_id="ACC-P-01",
            customer_id="CUST-P-01",
            amount=85.00,
            currency="USD",
            channel="POS_CHIP",
            counterparty_account="ACC-P-WHOLEFOODS",
            counterparty_name="WHOLE FOODS MARKET",
            counterparty_bank="JPMorgan Chase",
            counterparty_country="US",
            origin_country="US",
            destination_country="US",
            memo="Grocery wholesale purchase",
        ),
        evidence_records=[],
    )
    report = run_validated_workflow(case)
    data = report.model_dump()

    # Required keys for App.jsx, AgentStepperPanel.jsx, DossierPanel.jsx
    assert "preliminary_risk_level" in data
    assert "decision" in data
    assert "sar_recommendation" in data
    assert "grounding_status" in data
    assert "risk_dimensions" in data
    assert "telemetry_probes" in data
    assert "anomaly_score" in data
    assert "anomaly_details" in data
    assert data["grounding_status"] == "FULLY_GROUNDED"
    assert data["decision"] == "RELEASE_WITH_PROVENANCE"
