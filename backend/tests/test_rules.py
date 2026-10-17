"""
Tests for Deterministic Transaction Risk Rules.
"""

from backend.app.schemas import Transaction, EvidenceRecord, InvestigationCase
from backend.app.rules import (
    evaluate_large_amount,
    evaluate_structuring,
    evaluate_high_risk_jurisdiction,
    evaluate_velocity_anomaly,
    evaluate_sanctions_match,
    evaluate_kyc_status,
)


def make_sample_transaction(amount=5000.0, country="US", memo="Invoice"):
    return Transaction(
        transaction_id="TXN-001",
        timestamp="2026-10-12T14:00:00Z",
        account_id="ACC-001",
        customer_id="CUST-001",
        amount=amount,
        currency="USD",
        channel="WIRE",
        counterparty_account="CP-001",
        counterparty_name="Acme Corp",
        counterparty_bank="Bank of Test",
        counterparty_country=country,
        memo=memo,
        is_synthetic=True
    )


def test_large_amount_threshold():
    tx_small = make_sample_transaction(amount=9500.0)
    tx_large = make_sample_transaction(amount=15000.0)
    assert evaluate_large_amount(tx_small).flagged is False
    assert evaluate_large_amount(tx_large).flagged is True


def test_structuring_rule():
    tx_normal = make_sample_transaction(amount=8500.0)
    tx_smurf = make_sample_transaction(amount=9850.0)
    tx_large = make_sample_transaction(amount=10500.0)

    assert evaluate_structuring(tx_normal).flagged is False
    assert evaluate_structuring(tx_smurf).flagged is True
    assert evaluate_structuring(tx_large).flagged is False


def test_high_risk_jurisdiction():
    tx_us = make_sample_transaction(country="US")
    tx_kp = make_sample_transaction(country="KP")
    tx_ky = make_sample_transaction(country="KY")

    assert evaluate_high_risk_jurisdiction(tx_us).flagged is False
    assert evaluate_high_risk_jurisdiction(tx_kp).flagged is True
    assert evaluate_high_risk_jurisdiction(tx_ky).flagged is True


def test_velocity_anomaly():
    tx = make_sample_transaction(amount=25000.0)
    history_rec = EvidenceRecord(
        evidence_id="EVID-HIST",
        evidence_type="ACCOUNT_HISTORY",
        timestamp="2026-10-12T10:00:00Z",
        source_system="Ledger",
        data={"avg_30d_transaction_amount": 2000.0},
        is_synthetic=True
    )
    # 25,000 / 2,000 = 12.5x (> 5x threshold)
    res = evaluate_velocity_anomaly(tx, [history_rec])
    assert res.flagged is True


def test_velocity_anomaly_suppressed_for_low_value():
    tx_small = make_sample_transaction(amount=142.50)
    history_rec = EvidenceRecord(
        evidence_id="EVID-HIST",
        evidence_type="ACCOUNT_HISTORY",
        timestamp="2026-10-12T10:00:00Z",
        source_system="Ledger",
        data={"avg_30d_transaction_amount": 10.0},
        is_synthetic=True
    )
    # 142.50 / 10 = 14.25x, but under $500 threshold must return INFO severity
    res = evaluate_velocity_anomaly(tx_small, [history_rec])
    assert res.severity == "INFO"
    assert res.flagged is False


def test_kyc_status_missing_evidence_is_info():
    # Missing optional KYC evidence must yield INFO, not HIGH
    res = evaluate_kyc_status([])
    assert res.severity == "INFO"
    assert res.flagged is False


def test_kyc_status_unverified_low_value_is_low_severity():
    tx_small = make_sample_transaction(amount=142.50)
    kyc_unverified = EvidenceRecord(
        evidence_id="EVID-KYC",
        evidence_type="KYC_PROFILE",
        timestamp="2026-10-12T10:00:00Z",
        source_system="Core",
        data={"verification_status": "UNVERIFIED"},
        is_synthetic=True
    )
    res = evaluate_kyc_status([kyc_unverified], tx_small)
    assert res.severity == "LOW"
