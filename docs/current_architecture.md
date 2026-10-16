# Ceylix AI: Current Architecture & File Structure

> **Project:** Ceylix AI — Evidence-Grounded Transaction Risk Assistant  
> **Repository:** `c:\Users\Asus\Downloads\ceylix-ai`  
> **Status:** Working Prototype & Benchmarking Pipeline Implemented  
> **Updated:** October 2026  

---

## 1. System Architecture Diagram

```text
                           Case Payload (Transaction + Evidence Bundle)
                                                |
                        +-----------------------+-----------------------+
                        |                                               |
                        v                                               v
            [ Workflow A: Baseline ]                       [ Workflow B: Validated ]
                        |                                               |
             Google Gemini 2.5 Flash                         Deterministic Risk Rules
             (Via OpenRouter or GenAI)                       (7 Inspectable BFSI Rules)
                        |                                               |
               Raw Claims & Summary                          Google Gemini 2.5 Flash
                        |                                               |
          (Accepted Without Checking)                      Deterministic Evidence Validator
                        |                                  - Provenance & ID check
                        v                                  - Field-value reconciliation
             Released Report (Unverified)                  - SLA freshness verification
                                                           - Contradiction detection
                                                           - Prompt injection defense
                                                                        |
                                                             Review Policy Engine
                                                                        |
                                                           +------------+------------+
                                                           |                         |
                                                           v                         v
                                                 Release with Provenance    Abstain for Review
```

---

## 2. What Has Been Completed

### A. Core Backend Engine
1. **Pydantic Schemas (`backend/app/schemas.py`)**: Defined strict contracts for transactions, evidence records, cases, expected outcomes, claims, rules, and reports. All benchmark data carries synthetic provenance flags.
2. **7 Deterministic Rules (`backend/app/rules.py`)**: Transparent rules for Large Amount (≥$10k), Structuring ($9k–$10k), High-Risk Jurisdictions (`KP`, `IR`, `KY`, `PA`), Velocity Anomaly (>5x baseline), Device Mismatch, Sanctions Watchlist Hits, and KYC Status.
3. **Evidence Validator (`backend/app/evidence_validator.py`)**: Validates claim-level evidence IDs, verifies field values against source records, checks freshness SLAs (KYC: 730d, Sanctions: 24h, Device: 90d), flags contradictions (impossible travel, 10x amount mismatches), and catches prompt injection in memos.
4. **Governance Review Policy (`backend/app/review_policy.py`)**: Translates validation findings into formal dispositions (`RELEASE_WITH_PROVENANCE`, `RELEASE_QUALIFIED`, `ABSTAIN_FOR_HUMAN_REVIEW`) with defect reason codes.
5. **Gemini Service (`backend/app/gemini_service.py`)**: Handles model prompting and structured JSON parsing via OpenRouter (`google/gemini-2.5-flash`) or Google GenAI SDK, with an offline simulation fallback.
6. **Workflow Orchestrators (`backend/app/workflows.py`)**: Coordinates Workflow A (unvalidated baseline) and Workflow B (validated with deterministic grounding).
7. **FastAPI Application (`backend/app/main.py`)**: REST endpoints for baseline investigation, validated investigation, rules, claim validation, case browsing, and `/health`.

### B. Synthetic Benchmark & External Grounding
1. **Dataset Generator (`research/generator/dataset_generator.py`)**: Generates 60 reproducible test cases across 6 categories (Seed: 42). Keeps model inputs (`cases.json`) separate from ground truth labels (`expected_outcomes.json`).
2. **External Data Adapter (`research/generator/external_data_adapter.py`)**:
   - **Kaggle `creditcardfraud`**: Cached via `kagglehub` to calibrate empirical amounts (mean: $63.03, median: $15.95, 95th pct: $250.00).
   - **IBM AMLSim**: Multi-agent typologies for structuring, fan-in aggregation, velocity burst, and jurisdiction layering.
   - **CFPB API**: Real-world consumer dispute and unauthorized transfer narratives.

### C. Evaluation & Tests
1. **Evaluation Engine (`research/evaluation/metrics.py`, `run_experiment.py`)**: Measures unsupported-claim rate, correct abstention rate, false rejection rate, evidence traceability, and latency percentiles.
2. **Automated Test Suite (`backend/tests/`)**: 14 unit and integration tests covering rules, validator, generator reproducibility, and comparative workflows (100% passing).
3. **Execution Runners**: `pytest.ini` and `conftest.py` in both root and backend directories allow running tests and scripts from any directory.

---

## 3. Current Available File Structure

```text
ceylix-ai/
├── README.md                                    # Main project documentation and findings
├── pytest.ini                                   # Root pytest configuration
├── .env.example                                 # Environment variable template
│
├── docs/
│   ├── current_architecture.md                  # This document
│   └── development_overview.md                  # Detailed research & implementation overview
│
├── backend/
│   ├── pytest.ini                               # Backend directory pytest config
│   ├── conftest.py                              # Path discovery fixture
│   ├── requirements.txt                         # Dependencies (fastapi, uvicorn, pydantic, etc.)
│   ├── run_generator.py                         # One-command dataset generator runner
│   ├── run_experiment.py                        # One-command experiment runner
│   │
│   ├── app/
│   │   ├── __init__.py                          # App package initializer with sys.path bootstrap
│   │   ├── main.py                              # FastAPI server endpoints
│   │   ├── schemas.py                           # Pydantic data models
│   │   ├── rules.py                             # 7 deterministic BFSI risk rules
│   │   ├── gemini_service.py                    # Gemini API & simulation integration
│   │   ├── evidence_validator.py                # Deterministic claim verification engine
│   │   ├── review_policy.py                     # Abstention & governance engine
│   │   └── workflows.py                         # Workflow A vs Workflow B orchestrators
│   │
│   └── tests/
│       ├── __init__.py                          # Tests package initializer
│       ├── conftest.py                          # Path resolution fixture for test runner
│       ├── test_generator.py                    # Unit tests for dataset generation
│       ├── test_rules.py                        # Unit tests for risk rules
│       ├── test_validator.py                    # Unit tests for claim validator
│       └── test_workflows_and_metrics.py        # Integration tests for workflows & metrics
│
└── research/
    ├── __init__.py                              # Research package initializer
    ├── evaluation_protocol.md                   # Evaluation protocol documentation
    │
    ├── data/
    │   ├── cases.json                           # 60 synthetic benchmark test cases (model inputs)
    │   ├── expected_outcomes.json               # Ground truth labels & defect codes
    │   └── benchmark_dataset_summary.json       # Distribution & external benchmark metadata
    │
    ├── generator/
    │   ├── __init__.py                          # Generator package initializer
    │   ├── dataset_generator.py                 # Synthetic dataset generator (Seed: 42)
    │   └── external_data_adapter.py             # Kaggle, AMLSim, and CFPB adapter
    │
    ├── evaluation/
    │   ├── __init__.py                          # Evaluation package initializer
    │   ├── metrics.py                           # Metric computation logic
    │   └── run_experiment.py                    # Benchmark experiment runner
    │
    └── results/
        ├── experiment_results.json              # Full raw benchmark results
        └── experiment_summary.md                # Markdown comparison table
```

---

## 4. Empirical Benchmark Results

Measured across 60 reproducible test cases (Seed: 42):

| Metric | Workflow A (Baseline) | Workflow B (Validated) | Delta |
|---|---|---|---|
| **Unsupported-Claim Rate** | **31.9%** (51/160) | **0.0%** (0/160) | **-31.9%** |
| **Correct Abstention Rate** | **0.0%** (0/40) | **100.0%** (40/40) | **+100.0%** |
| **False Rejection Rate (FRR)** | **0.0%** (0/20) | **0.0%** (0/20) | **0.0%** |
| **Evidence Traceability** | **81.2%** | **81.2%** | Preserved |
| **Median Latency** | **20.4 ms** | **41.1 ms** | **+20.7 ms** |

---

## 5. Quick Run Commands

### From Repository Root (`ceylix-ai/`):
```bash
# Run tests
python -m pytest -v

# Generate dataset
python -m research.generator.dataset_generator

# Run benchmark experiment
python -m research.evaluation.run_experiment --simulate

# Start API server
uvicorn backend.app.main:app --reload --port 8000
```

### From Backend Directory (`ceylix-ai/backend/`):
```bash
# Run tests
python -m pytest -v

# Generate dataset
python run_generator.py

# Run benchmark experiment
python run_experiment.py --simulate

# Start API server
uvicorn app.main:app --reload --port 8000
```
