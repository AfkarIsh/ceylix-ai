"""
Integration tests for Workflows and Benchmark Metrics.
"""

from research.generator.dataset_generator import generate_benchmark_dataset, FIXED_SEED
from backend.app.workflows import run_baseline_workflow, run_validated_workflow
from research.evaluation.metrics import compute_workflow_metrics


def test_baseline_vs_validated_workflow():
    cases, outcomes = generate_benchmark_dataset(seed=FIXED_SEED)
    outcome_map = {o.case_id: o for o in outcomes}

    # Test an untrusted instruction case (e.g. CASE-041)
    injection_case = next(c for c in cases if c.category == "untrusted_instructions")
    rep_a = run_baseline_workflow(injection_case, force_simulation=True)
    rep_b = run_validated_workflow(injection_case, force_simulation=True)

    # In baseline, the injection succeeds in suppressing abstention
    assert rep_a.decision == "RELEASE_WITH_PROVENANCE"
    # In validated workflow, the deterministic validator detects injection and forces abstention
    assert rep_b.decision == "ABSTAIN_FOR_HUMAN_REVIEW"
    assert "UNTRUSTED_INSTRUCTION_ATTEMPT_DETECTED" in rep_b.abstention_reasons


def test_metrics_computation():
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

    reps_a = [run_baseline_workflow(c, force_simulation=True) for c in subset_cases]
    reps_b = [run_validated_workflow(c, force_simulation=True) for c in subset_cases]

    metrics_a = compute_workflow_metrics("baseline_unvalidated", reps_a, subset_cases, outcome_map)
    metrics_b = compute_workflow_metrics("validated_deterministic", reps_b, subset_cases, outcome_map)

    # Validated workflow should have lower unsupported claim rate and higher correct abstention rate
    assert metrics_b.unsupported_claim_rate <= metrics_a.unsupported_claim_rate
    assert metrics_b.correct_abstention_rate > metrics_a.correct_abstention_rate
    assert metrics_b.false_rejection_rate == 0.0
