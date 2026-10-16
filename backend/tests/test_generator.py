"""
Tests for Synthetic Dataset Generator.
Verifies reproducibility, category distribution, synthetic labeling, and separation of outcomes.
"""

import json
from research.generator.dataset_generator import generate_benchmark_dataset, FIXED_SEED
from backend.app.schemas import InvestigationCase, ExpectedOutcome


def test_generator_reproducibility():
    """Verify that generating with fixed seed produces identical output."""
    cases1, outcomes1 = generate_benchmark_dataset(seed=FIXED_SEED)
    cases2, outcomes2 = generate_benchmark_dataset(seed=FIXED_SEED)

    assert len(cases1) == 60
    assert len(outcomes1) == 60

    # Ensure identical case IDs and amounts
    for c1, c2 in zip(cases1, cases2):
        assert c1.case_id == c2.case_id
        assert c1.transaction.amount == c2.transaction.amount
        assert c1.category == c2.category

    for o1, o2 in zip(outcomes1, outcomes2):
        assert o1.case_id == o2.case_id
        assert o1.expected_abstention == o2.expected_abstention
        assert o1.ground_truth_risk == o2.ground_truth_risk


def test_generator_categories_distribution():
    """Verify exactly 10 cases across all 6 categories."""
    cases, outcomes = generate_benchmark_dataset(seed=FIXED_SEED)
    categories = [
        "complete_consistent",
        "missing_evidence",
        "conflicting_evidence",
        "stale_evidence",
        "untrusted_instructions",
        "benign_and_suspicious_controls"
    ]

    for cat in categories:
        count = sum(1 for c in cases if c.category == cat)
        assert count == 10, f"Category {cat} has {count} cases, expected 10."


def test_synthetic_data_labeling():
    """Verify every case is clearly labeled as synthetic."""
    cases, _ = generate_benchmark_dataset(seed=FIXED_SEED)
    for c in cases:
        assert c.is_synthetic is True
        assert "SYNTHETIC" in c.synthetic_disclaimer.upper()
        assert c.transaction.is_synthetic is True
        for ev in c.evidence_records:
            assert ev.is_synthetic is True


def test_outcomes_separation():
    """Verify model inputs in InvestigationCase do not contain expected ground truth labels."""
    cases, outcomes = generate_benchmark_dataset(seed=FIXED_SEED)
    outcome_map = {o.case_id: o for o in outcomes}

    for c in cases:
        case_dict = c.model_dump()
        # Verify no ground truth leaked into model input payload
        assert "ground_truth_risk" not in case_dict
        assert "expected_abstention" not in case_dict
        assert "expected_abstention_reasons" not in case_dict
        assert c.case_id in outcome_map
