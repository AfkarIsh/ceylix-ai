"""
Review Policy and Abstention Governance Engine for Ceylix AI.
Determines whether an investigation report can be released or must abstain
for human review based on deterministic validation outcomes and rule results.
"""

from typing import List, Tuple, Literal
try:
    from backend.app.schemas import RuleEvaluationResult, Claim
    from backend.app.evidence_validator import ValidationReport
except ModuleNotFoundError:
    from app.schemas import RuleEvaluationResult, Claim
    from app.evidence_validator import ValidationReport


def evaluate_review_policy(
    validation_report: ValidationReport,
    rule_results: List[RuleEvaluationResult],
    preliminary_risk: str,
) -> Tuple[
    Literal["RELEASE_WITH_PROVENANCE", "RELEASE_QUALIFIED", "ABSTAIN_FOR_HUMAN_REVIEW"],
    bool, # abstain_recommended
    List[str], # abstention_reasons
    List[str]  # warnings
]:
    """
    Evaluate deterministic governance rules to determine final report disposition.
    Returns: (decision, abstain_recommended, abstention_reasons, warnings)
    """
    abstention_reasons: List[str] = []
    warnings: List[str] = list(validation_report.validation_warnings)

    # 1. Untrusted Prompt Injection Detection -> Mandatory Abstention
    if validation_report.untrusted_instruction_detected:
        abstention_reasons.append("UNTRUSTED_INSTRUCTION_ATTEMPT_DETECTED")
        for detail in validation_report.untrusted_instruction_details:
            warnings.append(detail)

    # 2. Evidence Contradictions -> Mandatory Abstention
    if validation_report.detected_conflicts:
        abstention_reasons.append("CONTRADICTORY_EVIDENCE_DETECTED")
        for conf in validation_report.detected_conflicts:
            abstention_reasons.append(f"CONFLICT:{conf['type']}")

    # 3. Missing Mandatory Evidence -> Mandatory Abstention
    if validation_report.missing_required_evidence:
        abstention_reasons.append("MISSING_MANDATORY_EVIDENCE")
        for m in validation_report.missing_required_evidence:
            abstention_reasons.append(f"MISSING_EVIDENCE_TYPE:{m}")

    # 4. Critical Stale Evidence -> Mandatory Abstention
    if validation_report.stale_evidence_ids:
        abstention_reasons.append("STALE_CRITICAL_EVIDENCE")
        for sid in validation_report.stale_evidence_ids:
            abstention_reasons.append(f"EXPIRED_EVIDENCE_ID:{sid}")

    # 5. Unsupported Factual Claims -> Mandatory Abstention
    if validation_report.unsupported_claims_count > 0:
        abstention_reasons.append(
            f"UNSUPPORTED_CLAIMS_DETECTED:{validation_report.unsupported_claims_count}_CLAIMS"
        )

    # 6. High Severity Deterministic Rule Flags on Incomplete Data
    high_severity_flags = [r for r in rule_results if r.flagged and r.severity == "HIGH"]
    if high_severity_flags:
        for r in high_severity_flags:
            warnings.append(f"High risk rule flag: {r.rule_name} - {r.details}")

    # Final Decision Calculation
    if abstention_reasons:
        decision = "ABSTAIN_FOR_HUMAN_REVIEW"
        abstain_recommended = True
    elif warnings:
        decision = "RELEASE_QUALIFIED"
        abstain_recommended = False
    else:
        decision = "RELEASE_WITH_PROVENANCE"
        abstain_recommended = False

    return decision, abstain_recommended, abstention_reasons, warnings
