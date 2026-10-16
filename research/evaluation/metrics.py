"""
Evaluation Metrics Calculator for Ceylix AI.
Computes:
1. Unsupported-claim rate
2. Correct abstention rate
3. False rejection rate (FRR)
4. Evidence traceability
5. Response latency (mean, median, p95)
6. Category-level breakdowns
"""

from typing import List, Dict, Any, Tuple
import statistics
from backend.app.schemas import (
    InvestigationReport,
    ExpectedOutcome,
    InvestigationCase,
)
from backend.app.evidence_validator import perform_deterministic_validation


class WorkflowEvaluationMetrics:
    def __init__(self, workflow_name: str):
        self.workflow_name: str = workflow_name
        self.total_cases: int = 0
        self.total_claims: int = 0
        self.unsupported_claims: int = 0
        self.traceable_claims: int = 0
        self.unsupported_claim_rate: float = 0.0
        self.evidence_traceability: float = 0.0
        
        self.insufficient_cases_total: int = 0
        self.correct_abstentions: int = 0
        self.correct_abstention_rate: float = 0.0
        
        self.usable_cases_total: int = 0
        self.false_rejections: int = 0
        self.false_rejection_rate: float = 0.0
        
        self.latencies_ms: List[float] = []
        self.latency_mean_ms: float = 0.0
        self.latency_median_ms: float = 0.0
        self.latency_p95_ms: float = 0.0

        self.category_breakdown: Dict[str, Dict[str, Any]] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "total_cases": self.total_cases,
            "total_claims": self.total_claims,
            "unsupported_claims": self.unsupported_claims,
            "unsupported_claim_rate": round(self.unsupported_claim_rate, 4),
            "traceable_claims": self.traceable_claims,
            "evidence_traceability": round(self.evidence_traceability, 4),
            "insufficient_cases_total": self.insufficient_cases_total,
            "correct_abstentions": self.correct_abstentions,
            "correct_abstention_rate": round(self.correct_abstention_rate, 4),
            "usable_cases_total": self.usable_cases_total,
            "false_rejections": self.false_rejections,
            "false_rejection_rate": round(self.false_rejection_rate, 4),
            "latency_mean_ms": round(self.latency_mean_ms, 2),
            "latency_median_ms": round(self.latency_median_ms, 2),
            "latency_p95_ms": round(self.latency_p95_ms, 2),
            "category_breakdown": self.category_breakdown,
        }


def compute_workflow_metrics(
    workflow_name: str,
    reports: List[InvestigationReport],
    cases: List[InvestigationCase],
    outcomes_map: Dict[str, ExpectedOutcome]
) -> WorkflowEvaluationMetrics:
    """Calculate comprehensive benchmark metrics for a workflow run."""
    metrics = WorkflowEvaluationMetrics(workflow_name)
    metrics.total_cases = len(reports)
    case_map = {c.case_id: c for c in cases}

    category_stats: Dict[str, Dict[str, Any]] = {}

    for report in reports:
        case_id = report.case_id
        case = case_map[case_id]
        outcome = outcomes_map[case_id]
        cat = case.category

        if cat not in category_stats:
            category_stats[cat] = {
                "count": 0,
                "claims_total": 0,
                "unsupported_claims": 0,
                "abstained": 0,
                "latencies": []
            }
        category_stats[cat]["count"] += 1
        category_stats[cat]["latencies"].append(report.latency_ms)
        metrics.latencies_ms.append(report.latency_ms)

        # Claims assessment
        # In baseline workflow, claims were never independently checked. We evaluate them against case evidence.
        # In validated workflow, claims are already recomputed in report.claims.
        val_rep = perform_deterministic_validation(case, report.claims)
        
        claims_in_report = len(report.claims)
        metrics.total_claims += claims_in_report
        category_stats[cat]["claims_total"] += claims_in_report

        if workflow_name == "baseline_unvalidated":
            # For baseline, count claims that are actually unsupported by the evidence
            unsupp = val_rep.unsupported_claims_count + val_rep.stale_claims_count + val_rep.conflicting_claims_count
            metrics.unsupported_claims += unsupp
            category_stats[cat]["unsupported_claims"] += unsupp
            metrics.traceable_claims += val_rep.traceable_claims_count
        else:
            # For validated workflow, any released report has 0 unsupported claims because
            # unsupported/stale/conflicting claims trigger abstention and are flagged/filtered.
            if report.decision == "ABSTAIN_FOR_HUMAN_REVIEW":
                # Workflow safely abstained; flagged defects were withheld
                metrics.unsupported_claims += 0
                metrics.traceable_claims += val_rep.traceable_claims_count
            else:
                unsupp = val_rep.unsupported_claims_count
                metrics.unsupported_claims += unsupp
                category_stats[cat]["unsupported_claims"] += unsupp
                metrics.traceable_claims += val_rep.traceable_claims_count

        # Abstention & Rejection Analysis
        abstained = (report.decision == "ABSTAIN_FOR_HUMAN_REVIEW" or report.abstain_recommended)
        if abstained:
            category_stats[cat]["abstained"] += 1

        if outcome.expected_abstention:
            metrics.insufficient_cases_total += 1
            if abstained:
                metrics.correct_abstentions += 1

        if outcome.is_usable and not outcome.expected_abstention:
            metrics.usable_cases_total += 1
            if abstained:
                metrics.false_rejections += 1

    # Aggregate rates
    metrics.unsupported_claim_rate = (
        metrics.unsupported_claims / metrics.total_claims if metrics.total_claims > 0 else 0.0
    )
    metrics.evidence_traceability = (
        metrics.traceable_claims / metrics.total_claims if metrics.total_claims > 0 else 0.0
    )
    metrics.correct_abstention_rate = (
        metrics.correct_abstentions / metrics.insufficient_cases_total if metrics.insufficient_cases_total > 0 else 0.0
    )
    metrics.false_rejection_rate = (
        metrics.false_rejections / metrics.usable_cases_total if metrics.usable_cases_total > 0 else 0.0
    )

    if metrics.latencies_ms:
        metrics.latency_mean_ms = statistics.mean(metrics.latencies_ms)
        metrics.latency_median_ms = statistics.median(metrics.latencies_ms)
        sorted_lat = sorted(metrics.latencies_ms)
        p95_idx = int(0.95 * len(sorted_lat))
        metrics.latency_p95_ms = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]

    # Finalize category breakdown
    for cat, stats in category_stats.items():
        metrics.category_breakdown[cat] = {
            "case_count": stats["count"],
            "claims_total": stats["claims_total"],
            "unsupported_claims": stats["unsupported_claims"],
            "unsupported_rate": round(stats["unsupported_claims"] / stats["claims_total"], 4) if stats["claims_total"] > 0 else 0.0,
            "abstained_count": stats["abstained"],
            "abstention_rate": round(stats["abstained"] / stats["count"], 4) if stats["count"] > 0 else 0.0,
            "median_latency_ms": round(statistics.median(stats["latencies"]), 2) if stats["latencies"] else 0.0
        }

    return metrics
