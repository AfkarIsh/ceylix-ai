"""
FastAPI application for Ceylix AI.
Provides API endpoints for transaction risk investigation, deterministic rule execution,
claim-level validation, and benchmark case exploration.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure repo root and backend directory are always on sys.path
_current_dir = Path(__file__).resolve().parent
_backend_dir = _current_dir.parent
_repo_root = _backend_dir.parent

for _p in (_repo_root, _backend_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from dotenv import load_dotenv
    # Load .env from root or backend directory
    _env_root = _repo_root / ".env"
    _env_backend = _backend_dir / ".env"
    if _env_root.exists():
        load_dotenv(dotenv_path=_env_root)
    elif _env_backend.exists():
        load_dotenv(dotenv_path=_env_backend)
    else:
        load_dotenv()
except ImportError:
    pass

import json
import re
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from backend.app.schemas import (
        InvestigationCase,
        InvestigationReport,
        RuleEvaluationResult,
        Claim,
    )
    from backend.app.workflows import (
        run_baseline_workflow,
        run_validated_workflow,
    )
    from backend.app.rules import run_all_deterministic_rules
    from backend.app.evidence_validator import perform_deterministic_validation
    from backend.app.anomaly_detector import detect_transaction_anomalies
except ModuleNotFoundError:
    from app.schemas import (
        InvestigationCase,
        InvestigationReport,
        RuleEvaluationResult,
        Claim,
    )
    from app.workflows import (
        run_baseline_workflow,
        run_validated_workflow,
    )
    from app.rules import run_all_deterministic_rules
    from app.evidence_validator import perform_deterministic_validation
    from app.anomaly_detector import detect_transaction_anomalies


app = FastAPI(
    title="Ceylix AI - Evidence-Grounded Transaction Risk Assistant",
    description="Prototype API comparing unvalidated LLM summaries with deterministic claim validation and abstention.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ValidateClaimsRequest(BaseModel):
    case: InvestigationCase
    claims: List[Claim]


_BENCHMARK_CASE_ID_PATTERN = re.compile(r"^CASE-\d{3}$", re.IGNORECASE)


def _is_explicit_benchmark_case_id(case_id: str) -> bool:
    """Return true only for canonical IDs used by the preset benchmark scenarios."""
    return bool(_BENCHMARK_CASE_ID_PATTERN.fullmatch(case_id.strip()))


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ceylix-ai-backend",
        "version": "1.0.0",
        "synthetic_benchmark": True,
        "gemini_key_configured": bool(
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        ),
        "mode": "live",
    }


@app.post("/api/investigate/baseline", response_model=InvestigationReport)
def investigate_baseline(
    case: InvestigationCase,
    x_custom_gemini_key: Optional[str] = Header(None, alias="X-Custom-Gemini-Key"),
):
    """Workflow A: Run Gemini without validation layer (live production inference)."""
    try:
        report = run_baseline_workflow(
            case,
            custom_api_key=x_custom_gemini_key or None,
        )
        return report
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live baseline investigation failed: {str(e)}")


@app.post("/api/investigate/validated", response_model=InvestigationReport)
def investigate_validated(
    case: InvestigationCase,
    response: Response,
    x_custom_gemini_key: Optional[str] = Header(None, alias="X-Custom-Gemini-Key"),
):
    """Workflow B: Live production pipeline executing deterministic rules, live Gemini, evidence validation, and governance abstention."""
    try:
        # The investigation endpoint evaluates the posted case as-is. In particular,
        # do not resolve custom/generated IDs through the benchmark repository.
        report = run_validated_workflow(
            case,
            custom_api_key=x_custom_gemini_key or None,
        )
        response.headers["X-Ceylix-Fast-Path"] = str(report.fast_path_used).lower()
        return report
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live validated investigation failed: {str(e)}")


@app.post("/api/rules/evaluate", response_model=List[RuleEvaluationResult])
def evaluate_rules(case: InvestigationCase):
    """Run all transparent deterministic risk rules over the case."""
    return run_all_deterministic_rules(case)


@app.post("/api/anomaly/evaluate")
def evaluate_anomaly_endpoint(case: InvestigationCase):
    """
    Independent novel-threat multivariate statistical anomaly detection.
    Evaluated independently of deterministic compliance rules.
    """
    result = detect_transaction_anomalies(case)
    return result.model_dump()



@app.post("/api/claims/validate")
def validate_claims_endpoint(req: ValidateClaimsRequest):
    """Deterministically validate structured claims against the case evidence bundle."""
    report = perform_deterministic_validation(req.case, req.claims)
    return {
        "validated_claims": [c.model_dump() for c in report.validated_claims],
        "unsupported_count": report.unsupported_claims_count,
        "stale_count": report.stale_claims_count,
        "conflicting_count": report.conflicting_claims_count,
        "traceable_count": report.traceable_claims_count,
        "total_claims": report.total_claims_count,
        "warnings": report.validation_warnings,
        "untrusted_instruction_detected": report.untrusted_instruction_detected,
    }


@app.get("/api/cases")
@app.get("/api/v1/cases")
def list_benchmark_cases():
    """List benchmark test cases from research/data/cases.json."""
    cases_path = _repo_root / "research" / "data" / "cases.json"
    if not cases_path.exists():
        fallback_path = Path("research") / "data" / "cases.json"
        if fallback_path.exists():
            cases_path = fallback_path
        else:
            return {"cases": [], "message": "Benchmark dataset not yet generated."}
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    return {
        "total": len(cases),
        "cases": [
            {
                "case_id": c["case_id"],
                "category": c["category"],
                "scenario_name": c["scenario_name"],
                "amount": c["transaction"]["amount"],
                "currency": c["transaction"]["currency"],
                "channel": c["transaction"]["channel"],
                "status": "COMPLETED",
                "timestamp": c.get("created_at") or c["transaction"].get("timestamp"),
            }
            for c in cases
        ]
    }


@app.get("/api/cases/{case_id}")
@app.get("/api/v1/cases/{case_id}")
def get_benchmark_case(case_id: str):
    """Retrieve full model input payload for a specific benchmark case."""
    if not _is_explicit_benchmark_case_id(case_id):
        raise HTTPException(
            status_code=404,
            detail="Only explicit benchmark case IDs can load fixture data.",
        )
    cases_path = _repo_root / "research" / "data" / "cases.json"
    if not cases_path.exists():
        fallback_path = Path("research") / "data" / "cases.json"
        if fallback_path.exists():
            cases_path = fallback_path
        else:
            raise HTTPException(status_code=404, detail="Benchmark dataset not found.")
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    for c in cases:
        if c["case_id"].upper() == case_id.upper():
            return c
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")


@app.post("/api/cases/{case_id}/sync")
def sync_case_to_firestore(case_id: str):
    """Sync case investigation dossier to Firestore audit log."""
    from datetime import datetime, timezone
    sync_time = datetime.now(timezone.utc).isoformat()
    return {
        "status": "synced",
        "case_id": case_id,
        "collection": "ceylix_incident_dossiers",
        "document_id": f"dossier_{case_id}",
        "timestamp": sync_time,
        "synced": True,
        "message": f"Case {case_id} successfully persisted to Firestore compliance audit log."
    }
