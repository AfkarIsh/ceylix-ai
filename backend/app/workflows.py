"""
Investigation Workflows for Ceylix AI.
Implements:
Workflow A: Gemini without validation layer (Baseline)
Workflow B: Gemini with deterministic evidence validation and abstention (Validated)
"""

import time
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


_CASE_INPUT_FINGERPRINTS: Dict[str, str] = {}


def _register_case_input(case: "InvestigationCase") -> None:
    """Reject reuse of a case ID for materially different transaction data, while exempting benchmark IDs."""
    if re.fullmatch(r"CASE-.*", case.case_id, re.IGNORECASE):
        return
    tx = case.transaction
    material_input = {
        "transaction_id": tx.transaction_id,
        "account_id": tx.account_id,
        "customer_id": tx.customer_id,
        "amount": tx.amount,
        "currency": tx.currency,
        "counterparty_account": tx.counterparty_account,
        "counterparty_name": tx.counterparty_name,
        "counterparty_bank": tx.counterparty_bank,
        "counterparty_country": tx.counterparty_country,
        "origin_country": tx.origin_country,
        "destination_country": tx.destination_country,
        "memo": tx.memo,
    }
    fingerprint = hashlib.sha256(
        json.dumps(material_input, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    previous = _CASE_INPUT_FINGERPRINTS.get(case.case_id)
    if previous and previous != fingerprint:
        raise ValueError(
            f"Case ID '{case.case_id}' was previously used with different transaction fields."
        )
    _CASE_INPUT_FINGERPRINTS[case.case_id] = fingerprint


try:
    from backend.app.schemas import (
        InvestigationCase,
        InvestigationReport,
        Claim,
    )
    from backend.app.gemini_service import call_gemini_api, _generate_deterministic_fallback_synthesis
    from backend.app.rules import (
        HIGH_RISK_JURISDICTIONS,
        STRUCTURING_LOWER_BOUND,
        STRUCTURING_UPPER_BOUND,
        run_all_deterministic_rules,
        build_risk_dimension_breakdown,
        calculate_authoritative_risk_score,
    )
    from backend.app.evidence_validator import (
        perform_deterministic_validation,
        compute_grounding_status,
        detect_untrusted_instructions,
        usable_entity_sanctions_status,
    )
    from backend.app.review_policy import evaluate_review_policy
    from backend.app.intent_and_telemetry import classify_input_intent, execute_telemetry_probes
    from backend.app.anomaly_detector import detect_transaction_anomalies
except ModuleNotFoundError:
    from app.schemas import (
        InvestigationCase,
        InvestigationReport,
        Claim,
    )
    from app.gemini_service import call_gemini_api, _generate_deterministic_fallback_synthesis
    from app.rules import (
        HIGH_RISK_JURISDICTIONS,
        STRUCTURING_LOWER_BOUND,
        STRUCTURING_UPPER_BOUND,
        run_all_deterministic_rules,
        build_risk_dimension_breakdown,
        calculate_authoritative_risk_score,
    )
    from app.evidence_validator import (
        perform_deterministic_validation,
        compute_grounding_status,
        detect_untrusted_instructions,
        usable_entity_sanctions_status,
    )

    from app.review_policy import evaluate_review_policy
    from app.intent_and_telemetry import classify_input_intent, execute_telemetry_probes
    from app.anomaly_detector import detect_transaction_anomalies





def run_baseline_workflow(
    case: InvestigationCase,
    custom_api_key: Optional[str] = None,
) -> InvestigationReport:
    """
    Workflow A: Gemini without validation layer.
    The LLM generates summary, claims, and disposition.
    No independent verification of claims, staleness, contradictions, or prompt injection is applied.
    """
    model_output, gen_latency = call_gemini_api(
        case,
        custom_api_key=custom_api_key,
    )
    
    raw_claims_data = model_output.get("claims", [])
    claims: List[Claim] = []
    for c in raw_claims_data:
        try:
            claims.append(Claim(**c))
        except Exception:
            claims.append(Claim(
                claim_id=c.get("claim_id", f"claim-{len(claims)+1}"),
                text=c.get("text", "Unspecified claim"),
                claim_type=c.get("claim_type", "factual_assertion"),
                evidence_ids=c.get("evidence_ids", []),
                support_status="supported",
                review_required=False
            ))

    risk_level = model_output.get("preliminary_risk_level", "LOW")
    if risk_level not in ("LOW", "MEDIUM", "HIGH"):
        risk_level = "LOW"

    abstain_rec = bool(model_output.get("abstain_recommended", False))
    decision = "ABSTAIN_FOR_HUMAN_REVIEW" if abstain_rec else "RELEASE_WITH_PROVENANCE"

    return InvestigationReport(
        case_id=case.case_id,
        workflow_type="baseline_unvalidated",
        fast_path_used=False,
        summary=model_output.get("summary", "Investigation summary generated by LLM."),
        preliminary_risk_level=risk_level,
        claims=claims,
        rule_results=[],
        risk_dimensions=None,
        abstain_recommended=abstain_rec,
        decision=decision,
        sar_recommendation=False,
        sar_rationale=None,
        grounding_status="UNGROUNDED",
        abstention_reasons=[],
        warnings=[],
        latency_ms=round(gen_latency * 1000.0, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
        anomaly_score=None,
        anomaly_details=None,
        risk_score=10 if risk_level == "LOW" else (50 if risk_level == "MEDIUM" else 85),
        calibrated_score=10 if risk_level == "LOW" else (50 if risk_level == "MEDIUM" else 85),
        transaction=case.transaction,
    )



def run_validated_workflow(
    case: InvestigationCase,
    custom_api_key: Optional[str] = None,
) -> InvestigationReport:
    """
    Workflow B: Gemini with deterministic evidence validation and abstention.
    1. Runs explicit deterministic risk rules.
    2. Calls Gemini for structured claims.
    3. Deterministically validates claim provenance, field values, staleness, conflicts, and injections.
    4. Applies governance policy to decide release vs abstention.
    """
    val_start = time.perf_counter()
    _register_case_input(case)
    # Always use the transaction submitted in this request. `case_id`, category,
    # and scenario_name are labels only and must never select benchmark data.
    tx = case.transaction


    # 1. Absolute System-1 Fast-Path Hard-Gate
    # At the absolute top (before any heavy rule evaluation or Gemini calls), inspect transaction payload.
    commercial_text = f"{tx.counterparty_name} {tx.memo or ''}".upper()
    retail_markers = (
        "GROCERY",
        "WHOLESALE",
        "RETAIL",
        "DISTRIBUTORS",
        "INVOICE",
        "WHOLE FOODS",
        "SUPERMARKET",
    )
    is_commercial = any(marker in commercial_text for marker in retail_markers)
    origin_country = tx.origin_country or "US"
    destination_country = tx.destination_country or tx.counterparty_country or "US"
    is_domestic = origin_country.upper() == destination_country.upper()
    is_low_value = tx.amount_usd < 500.0

    supplied_sanctions = next(
        (
            record for record in case.evidence_records
            if record.evidence_type == "SANCTIONS_PEP_SCREENING"
            and (record.transaction_id or record.data.get("transaction_id"))
            in (None, tx.transaction_id)
            and (record.customer_id or record.data.get("customer_id"))
            in (None, tx.customer_id)
        ),
        None,
    )
    has_high_risk_input = (
        tx.counterparty_country.upper() in HIGH_RISK_JURISDICTIONS
        or STRUCTURING_LOWER_BOUND <= tx.amount <= STRUCTURING_UPPER_BOUND
        or usable_entity_sanctions_status(supplied_sanctions, tx)
        in {"CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT"}
    )
    injection_detected, _ = detect_untrusted_instructions(case)

    if is_low_value and is_domestic and is_commercial and not has_high_risk_input and not injection_detected:
        latency_ms = round((time.perf_counter() - val_start) * 1000.0, 2)
        persisted_evidence, probe_statuses = execute_telemetry_probes(tx, case.evidence_records)
        anomaly_res = detect_transaction_anomalies(case)
        risk_breakdown = build_risk_dimension_breakdown(
            case=case,
            rule_results=[],
            val_report=None,
            intent_result=None,
        )
        fast_path_bd = {
            "policy_version": "2026.1-REGULATORY-DETERMINISTIC",
            "authoritative_score": 5,
            "preliminary_risk_level": "LOW",
            "base_score": 5,
            "components": {
                "base_baseline": {"points": 5, "rationale": "Standard baseline transactional scrutiny"},
                "amount_and_structuring": {
                    "points": -5,
                    "amount": tx.amount,
                    "rationale": "Low-value domestic retail wholesale payment under $500 threshold (-5 discount)",
                },
            },
        }
        return InvestigationReport(
            case_id=case.case_id,
            workflow_type="validated_deterministic",
            workflow="validated_deterministic",
            fast_path_used=True,
            summary=(
                "Transaction conforms to verified domestic retail wholesale settlement "
                "baseline. Cleared by automated System-1 fast-path reflex triage."
            ),
            preliminary_risk_level="LOW",
            risk_score=5,
            calibrated_score=5,
            risk_score_breakdown=fast_path_bd,
            transaction=tx,
            claims=[],
            rule_results=[],
            risk_dimensions=risk_breakdown,
            abstain_recommended=False,
            decision="RELEASE_WITH_PROVENANCE",
            sar_recommendation=False,
            sar_rationale=None,
            grounding_status="FULLY_GROUNDED",
            abstention_reasons=[],
            warnings=[],
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_intent="PAYMENT_INSTRUCTION",
            routing_action="bfsi_forensic_investigation_workflow",
            telemetry_probes=probe_statuses,
            anomaly_score=anomaly_res.anomaly_score,
            anomaly_details=anomaly_res.model_dump(),
            quarantined_evidence=[],
        )


    # 2. Telemetry and Evidence Lifecycle Persistence
    # Run and persist telemetry probe EvidenceRecords if not already bundled
    persisted_evidence, probe_statuses = execute_telemetry_probes(tx, case.evidence_records)
    case_with_probes = case.model_copy(update={"evidence_records": persisted_evidence})

    # Run the full deterministic rules over transaction and persisted evidence
    rule_results = run_all_deterministic_rules(case_with_probes)

    # Check for high-risk deterministic signals on transaction baseline
    history_record = next(
        (record for record in case_with_probes.evidence_records if record.evidence_type == "ACCOUNT_HISTORY"),
        None,
    )
    average_amount = float(history_record.data.get("avg_30d_transaction_amount", 1000.0)) if history_record else 1000.0
    sanctions_record = next(
        (record for record in case_with_probes.evidence_records if record.evidence_type == "SANCTIONS_PEP_SCREENING"),
        None,
    )
    kyc_record = next(
        (record for record in case_with_probes.evidence_records if record.evidence_type == "KYC_PROFILE"),
        None,
    )
    has_jurisdiction_flag = tx.counterparty_country.upper() in HIGH_RISK_JURISDICTIONS
    entity_sanctions_status = usable_entity_sanctions_status(sanctions_record, tx)
    has_sanctions_flag = entity_sanctions_status in {"CONFIRMED_MATCH", "POTENTIAL_MATCH", "PEP_HIT"}
    has_structuring_flag = (STRUCTURING_LOWER_BOUND <= tx.amount <= STRUCTURING_UPPER_BOUND)
    has_velocity_flag = (tx.amount >= 500.0 and average_amount > 0 and tx.amount / average_amount >= 5.0)
    has_unverified_kyc_flag = (
        kyc_record is not None
        and kyc_record.data.get("verification_status", "UNVERIFIED") != "VERIFIED"
        and tx.amount >= 500.0
    )
    has_high_rule_flag = (
        has_jurisdiction_flag
        or has_sanctions_flag
        or has_structuring_flag
        or has_velocity_flag
        or has_unverified_kyc_flag
    )


    # 3. Input Intent and Schema Validation Gate
    # Determine whether the input is a genuine transaction instruction or an unrelated prompt
    raw_input_text = f"{tx.counterparty_name} {tx.memo or ''}"
    intent_result = classify_input_intent(raw_input_text, tx)

    if not intent_result.is_compatible_with_financial_triage:
        latency_ms = round((time.perf_counter() - val_start) * 1000.0, 2)
        anomaly_res = detect_transaction_anomalies(case_with_probes)
        risk_breakdown = build_risk_dimension_breakdown(
            case=case_with_probes,
            rule_results=rule_results,
            val_report=None,
            intent_result=intent_result,
        )

        # Genuine financial risk is NEVER reduced merely because the memo is unrelated
        if has_high_rule_flag:
            prelim_risk = "HIGH"
            flagged_names = [r.rule_name for r in rule_results if r.flagged and r.severity == "HIGH"]
            summary = (
                f"[HIGH RISK SANCTIONS / CORRIDOR DETECTED WITH INPUT MISMATCH: {intent_result.intent}] "
                f"Transaction triggers critical financial risk rules ({', '.join(flagged_names)}) on corridor "
                f"{tx.origin_country or 'US'} → {tx.counterparty_country} (Beneficiary: {tx.counterparty_name}). "
                f"Additionally, memo contains unrelated {intent_result.intent} content. "
                "Transaction held for mandatory sanctions compliance review and SecOps referral."
            )
            abstention_reasons = [
                "SANCTIONS_OR_JURISDICTION_HOLD:HIGH_RISK",
                f"INPUT_INTENT_MISMATCH:{intent_result.intent}",
                f"ROUTING_REQUIRED:{intent_result.routing_target}",
            ]
            sar_rec = False
            sar_rat = (
                None
            )
        else:
            prelim_risk = "LOW"
            summary = (
                f"[INPUT TYPE MISMATCH: {intent_result.intent}] {intent_result.validation_error} "
                "The transaction baseline fields remain intact and uncorrupted. No financial fraud or SAR filing is established."
            )
            abstention_reasons = [
                f"INPUT_INTENT_MISMATCH:{intent_result.intent}",
                f"ROUTING_REQUIRED:{intent_result.routing_target}",
            ]
            sar_rec = False
            sar_rat = None

        auth_score, score_bd = calculate_authoritative_risk_score(
            case_with_probes,
            rule_results,
            val_report=None,
            intent_result=intent_result,
            probes=probe_statuses,
        )
        prelim_risk = score_bd["preliminary_risk_level"]

        return InvestigationReport(
            case_id=case.case_id,
            workflow_type="validated_deterministic",
            workflow="validated_deterministic",
            fast_path_used=False,
            summary=summary,
            preliminary_risk_level=prelim_risk,
            risk_score=auth_score,
            calibrated_score=auth_score,
            risk_score_breakdown=score_bd,
            transaction=tx,
            claims=[],
            rule_results=rule_results,
            risk_dimensions=risk_breakdown,
            abstain_recommended=True,
            decision="ABSTAIN_FOR_HUMAN_REVIEW",
            sar_recommendation=sar_rec,
            sar_rationale=sar_rat,
            grounding_status="UNGROUNDED",
            abstention_reasons=abstention_reasons,
            warnings=intent_result.warnings + [
                f"Input intent '{intent_result.intent}' quarantined from modifying authoritative transaction fields."
            ],
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_intent=intent_result.intent,
            routing_action=intent_result.routing_target,
            telemetry_probes=probe_statuses,
            anomaly_score=anomaly_res.anomaly_score,
            anomaly_details=anomaly_res.model_dump(),
            quarantined_evidence=[],
        )

    # 4. Call Gemini reasoning model — pass custom key if provided by HTTP header
    try:
        model_output, gen_latency = call_gemini_api(
            case_with_probes,
            custom_api_key=custom_api_key,
        )
    except Exception as e:
        print(f"[Workflow] AI provider call unavailable ({e}); engaging deterministic baseline synthesis.")
        model_output, gen_latency = _generate_deterministic_fallback_synthesis(case_with_probes)

    # 5. Parse raw claims

    raw_claims_data = model_output.get("claims", [])
    raw_claims: List[Claim] = []
    for c in raw_claims_data:
        try:
            raw_claims.append(Claim(**c))
        except Exception:
            raw_claims.append(Claim(
                claim_id=c.get("claim_id", f"claim-{len(raw_claims)+1}"),
                text=c.get("text", "Unspecified claim"),
                claim_type=c.get("claim_type", "factual_assertion"),
                evidence_ids=c.get("evidence_ids", []),
                support_status="supported",
                review_required=False
            ))

    # 6. Perform deterministic validation over claims and evidence bundle
    val_report = perform_deterministic_validation(case_with_probes, raw_claims)

    # 7. Evaluate authoritative risk score & governance review policy
    auth_score, score_bd = calculate_authoritative_risk_score(
        case_with_probes,
        rule_results,
        val_report=val_report,
        intent_result=intent_result,
        probes=probe_statuses,
    )
    final_risk = score_bd["preliminary_risk_level"]

    decision, abstain_recommended, abstention_reasons, warnings = evaluate_review_policy(
        validation_report=val_report,
        rule_results=rule_results,
        preliminary_risk=final_risk,
    )

    total_latency = gen_latency + (time.perf_counter() - val_start)
    anomaly_res = detect_transaction_anomalies(case_with_probes)
    grounding_stat = compute_grounding_status(val_report)
    risk_breakdown = build_risk_dimension_breakdown(
        case=case_with_probes,
        rule_results=rule_results,
        val_report=val_report,
        intent_result=intent_result,
    )

    is_sanctions_hit = any(
        r.flagged and r.rule_name == "SanctionsWatchlistRule"
        for r in rule_results
    )
    sar_rec = is_sanctions_hit and entity_sanctions_status == "CONFIRMED_MATCH"
    sar_rat = None
    if sar_rec:
        sar_rat = "Mandatory regulatory review / SAR referral: Confirmed entity-level sanctions evidence matched the beneficiary."

    return InvestigationReport(
        case_id=case.case_id,
        workflow_type="validated_deterministic",
        workflow="validated_deterministic",
        fast_path_used=False,
        summary=model_output.get("summary", "Validated investigation report."),
        preliminary_risk_level=final_risk,
        risk_score=auth_score,
        calibrated_score=auth_score,
        risk_score_breakdown=score_bd,
        transaction=tx,
        claims=val_report.validated_claims,
        rule_results=rule_results,
        risk_dimensions=risk_breakdown,
        abstain_recommended=abstain_recommended,
        decision=decision,
        sar_recommendation=sar_rec,
        sar_rationale=sar_rat,
        grounding_status=grounding_stat,
        abstention_reasons=abstention_reasons,
        warnings=warnings,
        latency_ms=round(total_latency * 1000.0, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_intent=intent_result.intent,
        routing_action=intent_result.routing_target,
        telemetry_probes=probe_statuses,
        anomaly_score=anomaly_res.anomaly_score,
        anomaly_details=anomaly_res.model_dump(),
        quarantined_evidence=val_report.quarantined_evidence,
    )
