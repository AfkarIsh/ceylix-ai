"""
Integration tests for Workflows and Benchmark Metrics.
"""
from fastapi import Response

from research.generator.dataset_generator import generate_benchmark_dataset, FIXED_SEED
from backend.app.main import investigate_validated
from backend.app.workflows import run_baseline_workflow, run_validated_workflow
from research.evaluation.metrics import compute_workflow_metrics


def test_domestic_grocery_uses_fast_path_without_gemini(monkeypatch):
    cases, _ = generate_benchmark_dataset(seed=FIXED_SEED)
    grocery_case = next(
        case for case in cases
        if case.transaction.counterparty_name == "Whole Foods Market"
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Gemini must not be called for a clean domestic grocery wire")

    monkeypatch.setattr("backend.app.workflows.call_gemini_api", fail_if_called)
    monkeypatch.setattr(
        "backend.app.workflows.run_all_deterministic_rules",
        fail_if_called,
    )
    report = run_validated_workflow(grocery_case)

    assert report.fast_path_used is True
    assert report.workflow_type == "validated_deterministic"
    assert report.decision == "RELEASE_WITH_PROVENANCE"
    assert report.preliminary_risk_level == "LOW"
    assert report.latency_ms < 100.0
    assert report.rule_results == []


def _mock_llm_for_tests(case, *args, **kwargs):
    tx = case.transaction
    cat = case.category
    evidence_ids = [r.evidence_id for r in case.evidence_records]
    if cat == "untrusted_instructions":
        return {
            "summary": "Adversarial override accepted by LLM",
            "preliminary_risk_level": "LOW",
            "abstain_recommended": False,
            "claims": [
                {
                    "claim_id": "claim-001",
                    "text": "Authorized under executive treaty",
                    "claim_type": "factual_assertion",
                    "evidence_ids": [tx.transaction_id],
                }
            ],
        }, 0.05
    elif cat == "missing_evidence":
        return {
            "summary": "Hallucinated clean status",
            "preliminary_risk_level": "LOW",
            "abstain_recommended": False,
            "claims": [
                {
                    "claim_id": "claim-001",
                    "text": "Customer profile verified",
                    "claim_type": "factual_assertion",
                    "evidence_ids": ["EVID-NONEXISTENT"],
                }
            ],
        }, 0.05
    elif cat == "stale_evidence":
        return {
            "summary": "Accepted stale records",
            "preliminary_risk_level": "LOW",
            "abstain_recommended": False,
            "claims": [
                {
                    "claim_id": "claim-001",
                    "text": "Customer profile in good standing",
                    "claim_type": "factual_assertion",
                    "evidence_ids": [evidence_ids[0] if evidence_ids else tx.transaction_id],
                }
            ],
        }, 0.05
    elif cat == "conflicting_evidence":
        return {
            "summary": "Glossed over conflict",
            "preliminary_risk_level": "MEDIUM",
            "abstain_recommended": False,
            "claims": [
                {
                    "claim_id": "claim-001",
                    "text": "Activity recorded in logs",
                    "claim_type": "factual_assertion",
                    "evidence_ids": [evidence_ids[0] if evidence_ids else tx.transaction_id],
                }
            ],
        }, 0.05
    else:
        return {
            "summary": f"Transaction of ${tx.amount}",
            "preliminary_risk_level": "LOW",
            "abstain_recommended": False,
            "claims": [
                {
                    "claim_id": "claim-001",
                    "text": f"Amount is {tx.amount}",
                    "claim_type": "factual_assertion",
                    "evidence_ids": [tx.transaction_id],
                }
            ],
        }, 0.05


def test_domestic_grocery_fast_path_requires_no_high_rule_flags(monkeypatch):
    cases, _ = generate_benchmark_dataset(seed=FIXED_SEED)
    grocery_case = next(
        case for case in cases
        if case.transaction.counterparty_name == "Whole Foods Market"
    )
    # Transactions to high-risk foreign jurisdictions must not trigger the domestic fast path
    grocery_case.transaction.counterparty_country = "KP"
    grocery_case.transaction.destination_country = "KP"
    monkeypatch.setattr(
        "backend.app.workflows.call_gemini_api",
        lambda *args, **kwargs: (
            {"summary": "fallback", "claims": [], "preliminary_risk_level": "HIGH"},
            0.0,
        ),
    )

    report = run_validated_workflow(grocery_case)

    assert report.fast_path_used is False


def test_validated_endpoint_exposes_fast_path_header():
    cases, _ = generate_benchmark_dataset(seed=FIXED_SEED)
    grocery_case = next(
        case for case in cases
        if case.transaction.counterparty_name == "Whole Foods Market"
    )
    response = Response()

    report = investigate_validated(grocery_case, response)

    assert report.fast_path_used is True
    assert response.headers["X-Ceylix-Fast-Path"] == "true"
    assert report.workflow_type == "validated_deterministic"


def test_fast_path_does_not_apply_to_non_retail_or_over_limit_cases(monkeypatch):
    cases, _ = generate_benchmark_dataset(seed=FIXED_SEED)
    payroll_case = next(
        case for case in cases
        if case.transaction.counterparty_name == "Apex Technologies Corp"
    )
    monkeypatch.setattr(
        "backend.app.workflows.call_gemini_api",
        lambda *args, **kwargs: (
            {"summary": "fallback", "claims": [], "preliminary_risk_level": "LOW"},
            0.0,
        ),
    )

    report = run_validated_workflow(payroll_case)

    assert report.fast_path_used is False


def test_baseline_vs_validated_workflow(monkeypatch):
    monkeypatch.setattr("backend.app.workflows.call_gemini_api", _mock_llm_for_tests)
    cases, outcomes = generate_benchmark_dataset(seed=FIXED_SEED)
    outcome_map = {o.case_id: o for o in outcomes}

    # Test an untrusted instruction case (e.g. CASE-041)
    injection_case = next(c for c in cases if c.category == "untrusted_instructions")
    rep_a = run_baseline_workflow(injection_case)
    rep_b = run_validated_workflow(injection_case)

    # In baseline, the injection succeeds in suppressing abstention
    assert rep_a.decision == "RELEASE_WITH_PROVENANCE"
    # In validated workflow, the deterministic validator detects injection and forces abstention
    assert rep_b.decision == "ABSTAIN_FOR_HUMAN_REVIEW"
    assert "UNTRUSTED_INSTRUCTION_ATTEMPT_DETECTED" in rep_b.abstention_reasons


def test_metrics_computation(monkeypatch):
    monkeypatch.setattr("backend.app.workflows.call_gemini_api", _mock_llm_for_tests)
    cases, outcomes = generate_benchmark_dataset(seed=FIXED_SEED)
    outcome_map = {o.case_id: o for o in outcomes}

    # Run small slice of 6 cases (1 from each category)
    subset_cases = [next(c for c in cases if c.category == cat) for cat in [
        "complete_consistent",
        "missing_evidence",
        "conflicting_evidence",
        "stale_evidence",
        "untrusted_instructions",
        "benign_and_suspicious_controls"
    ]]

    reps_a = [run_baseline_workflow(c) for c in subset_cases]
    reps_b = [run_validated_workflow(c) for c in subset_cases]

    metrics_a = compute_workflow_metrics("baseline_unvalidated", reps_a, subset_cases, outcome_map)
    metrics_b = compute_workflow_metrics("validated_deterministic", reps_b, subset_cases, outcome_map)

    # Validated workflow should have lower unsupported claim rate and higher correct abstention rate
    assert metrics_b.unsupported_claim_rate <= metrics_a.unsupported_claim_rate
    assert metrics_b.correct_abstention_rate > metrics_a.correct_abstention_rate
    assert metrics_b.false_rejection_rate == 0.0


def test_scenario_a_case_051_fast_path_bypass():
    from backend.app.schemas import Transaction, InvestigationCase
    tx = Transaction(
        transaction_id="TX-051-WIRE-7741",
        timestamp="2026-10-16T09:14:22Z",
        account_id="acc_00514920",
        customer_id="CUST-1105",
        amount=142.50,
        currency="USD",
        channel="ONLINE_BANKING",
        origin_country="US",
        counterparty_name="Wholesale Grocery Distributors Inc",
        counterparty_account="US29WGDI000199284712",
        counterparty_bank="Bank of America, N.A.",
        counterparty_country="US",
        destination_country="US",
        memo="Net-30 wholesale grocery invoice settlement – ref: WGD-2026-0511",
    )
    case_051 = InvestigationCase(
        case_id="CASE-051",
        category="benign_and_suspicious_controls",
        scenario_name="⚡ Scenario A — Benign Wire",
        description="Analyst forensic triage for transaction TX-051-WIRE-7741",
        created_at="2026-10-16T09:14:22Z",
        transaction=tx,
        evidence_records=[],
    )
    report = run_validated_workflow(case_051)
    assert report.fast_path_used is True
    assert report.workflow == "validated_deterministic"
    assert report.workflow_type == "validated_deterministic"
    assert report.preliminary_risk_level == "LOW"
    assert report.decision == "RELEASE_WITH_PROVENANCE"
    assert report.latency_ms < 50.0
    assert report.claims == []
    assert report.rule_results == []
