# Ceylix AI
### Evidence-Grounded Transaction Risk Investigation Assistant

> **Project status:** In development  
> **Competition:** AI Builder Cup 2026  
> **Track:** BFSI (Banking, Financial Services and Insurance) — confirm the official track and eligibility requirements before submission.

Ceylix AI is a prototype that helps an analyst review a transaction-risk case by organizing available evidence, applying transparent deterministic checks, and using Google Gemini to produce a structured, evidence-linked explanation. A validation layer checks whether the generated claims are supported by the supplied evidence and flags missing, conflicting, stale, or untrusted information for human review.

**Ceylix AI supports investigation; it does not make final financial, legal, AML, KYC, or fraud determinations.**

---

### Research Contribution

Ceylix AI investigates the reliability of LLM-generated financial investigation reports under incomplete, stale, conflicting, and unavailable evidence conditions. The prototype compares an unvalidated Gemini workflow with a workflow that validates structured claims against recorded evidence and routes unresolved findings for human review.

We evaluate both approaches on a controlled synthetic benchmark using unsupported-claim rate, correct abstention rate, false rejection rate, evidence traceability, and latency. On the evaluated test set, the validation-enabled workflow achieved a **0.0% unsupported-claim rate** (compared with **31.9%** for the unvalidated workflow) and a **100.0% correct abstention rate** on insufficient-evidence cases (compared with **0.0%** for the baseline), while maintaining a **0.0% false rejection rate** on usable cases, **81.2% evidence traceability**, and a modest median latency overhead of **+20.8 ms**.

The contribution is an empirical evaluation of evidence-quality handling in this prototype, together with its implementation and reproducible test fixtures. It is not a claim to have invented LLM-assisted fraud investigation or deterministic rationale verification. Because the benchmark uses synthetic scenarios and a limited number of cases, the findings do not establish real-world fraud-detection effectiveness or production readiness.

---

## 1. Problem

Transaction-risk reviews can require analysts to examine scattered records and explain why a case needs further attention. A generative AI model can write fluent summaries, but fluency alone does not guarantee that every claim is supported by the evidence. Missing or contradictory records can lead to misleading explanations.

Ceylix AI explores whether a provenance-aware validation and abstention layer can make AI-generated investigation reports more traceable and safer to review.

## 2. Proposed Solution

The prototype is designed around five steps:

1. **Receive a case:** Load a transaction and its supplied evidence.
2. **Apply deterministic checks:** Run explicit, inspectable rules over available fields.
3. **Generate an explanation:** Ask Gemini for a structured summary of the case and the evidence relevant to each claim.
4. **Validate claims:** Check evidence references, field/value consistency, required fields, timestamps, and rule outcomes. Flag unsupported or conflicting claims rather than silently accepting them.
5. **Present review status:** Show the evidence, rule results, explanation, warnings, and whether human review is required.

A valid evidence ID alone does **not** prove that a statement is semantically supported. Validation should compare the actual referenced fields and values. Complex inferences must remain reviewable by a human.

## 3. Research Question

**Does a provenance-aware validation and abstention layer reduce unsupported claims in AI-generated financial investigation reports when evidence is missing, stale, contradictory, or unavailable, compared with the same LLM workflow without that layer?**

### Hypotheses to test

- **H1:** The validation workflow will produce a lower unsupported-claim rate than the baseline workflow.
- **H2:** The validation workflow will abstain or request review more appropriately when evidence is insufficient.
- **H3:** Validation may add latency or flag some otherwise usable reports, creating measurable trade-offs.

These are hypotheses, not results. Do not claim success until the tests have been run and the results recorded.

## 4. Scope and Safety

### In scope

- Synthetic transaction-risk cases for a competition demo.
- Transparent, deterministic rules with documented thresholds.
- Gemini-generated, structured explanations.
- Evidence references and claim-level validation.
- Missing, conflicting, stale, and untrusted evidence handling.
- Human-review flags and abstention when support is insufficient.
- Reproducible tests and baseline-versus-validation measurements.
- A simple web interface and cloud deployment, if completed and configured.

### Out of scope

- Real-world fraud detection accuracy claims without a properly authorized and representative dataset.
- Automatic blocking of transactions or accounts.
- Autonomous AML/SAR filing, KYC decisions, or legal determinations.
- Claims of zero hallucinations or guaranteed correctness.
- Use of real customer, account, payment-card, or other sensitive financial data in the demo.
- Treating IP geolocation or country mismatch alone as proof of fraud.

**Demo data:** Use clearly labelled synthetic data unless the team has explicit authorization to use another dataset. If external sanctions or risk data is integrated, record its source, retrieval time, permitted use, and freshness. Never imply that synthetic examples are live financial intelligence.

## 5. Planned Architecture

```text
React + Tailwind frontend
          |
          v
FastAPI backend
          |
          +--> Input/schema validation
          |
          +--> Deterministic risk rules
          |
          +--> Gemini structured explanation
          |
          +--> Evidence / claim validation
          |       |
          |       +--> Supported claims
          |       +--> Unsupported or conflicting claims
          |       +--> Abstention / human-review decision
          |
          v
Structured investigation result
          |
          +--> Firestore (case/results storage, if configured)
          +--> Analyst-facing UI

Deployment target (planned):
Frontend: Firebase Hosting
Backend: Google Cloud Run
Model: Google Gemini API
Storage: Firestore
```

This diagram describes the **intended architecture**, not proof that each service is already integrated. Update the status as implementation progresses.

## 6. Technology Stack

| Component | Planned technology | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Tailwind CSS | Analyst interface |
| API | Python, FastAPI, Pydantic | Request handling and schemas |
| LLM | Google Gemini API | Structured explanations |
| Database | Cloud Firestore | Case and result storage, if enabled |
| Frontend hosting | Firebase Hosting | Public web prototype |
| Backend hosting | Google Cloud Run | API deployment |
| Testing | pytest and documented test fixtures | Reproducible evaluation |
| Version control | Git and GitHub | Collaboration and submission |

Keep API keys in environment variables or a managed secret store. Never commit credentials to Git.

## 7. Core Data Contract

Use a structured response rather than relying on free-form prose alone. Adapt the exact schema as implementation progresses.

Example claim object:

```json
{
  "claim_id": "claim-001",
  "text": "The transaction amount exceeds the configured review threshold.",
  "claim_type": "rule_result",
  "evidence_ids": ["transaction-001"],
  "support_status": "supported",
  "review_required": false
}
```

Suggested `support_status` values:

- `supported`
- `unsupported`
- `conflicting`
- `stale`
- `insufficient_evidence`
- `requires_human_review`

Validate all fields and enum values on the backend. Do not trust a status supplied by the model without independently recomputing the validation outcome.

## 8. Evaluation Plan

Compare two workflows using the **same model, model settings, prompt where practical, and input cases**:

- **Baseline A:** Gemini generates the investigation report without the proposed validation/release layer.
- **Validated B:** Gemini generates the report, then deterministic validation checks its claims and decides whether to release, qualify, or abstain from the result.

### Initial test set

Create at least 60 synthetic cases, with 10 cases in each category:

1. Complete and consistent evidence.
2. Missing evidence.
3. Conflicting evidence.
4. Stale evidence.
5. Untrusted instructions embedded in evidence.
6. Benign and suspicious control cases.

Keep expected outcomes and test labels separate from the model prompt. Record the case IDs and exact test configuration so the experiment can be repeated.

### Metrics

| Metric | How to report it |
|---|---|
| Unsupported-claim rate | Unsupported factual claims divided by all assessed factual claims |
| Correct abstention rate | Insufficient-evidence cases correctly withheld or escalated divided by all insufficient-evidence cases |
| False rejection rate | Usable cases incorrectly blocked or escalated divided by all usable cases |
| Evidence traceability | Claims with valid, relevant evidence references divided by all claims requiring evidence |
| Median latency | Median end-to-end response time for each workflow |
| Review effort | Time or number of manual corrections required per case, if measured consistently |

Define the unit of measurement and labeling rules before running the test. Have a human review the claim labels; where possible, use two reviewers and resolve disagreements using a documented procedure. Report raw counts alongside percentages. Do not invent, round selectively, or present illustrative data as experimental results.

### 5. Running the Tests & Benchmark Experiment

**Step 1: Run the Pytest Test Suite**
```bash
python -m pytest -v
```
*(14 unit and integration tests passing covering generator reproducibility, deterministic rules, claim validation, and metrics computation).*

**Step 2: Regenerate the Benchmark Dataset (Seed: 42)**
```bash
python -m research.generator.dataset_generator
```

**Step 3: Run the Comparative Evaluation Experiment**

- *Hermetic Simulation Mode (Offline/Reproducible):*
  ```bash
  python -m research.evaluation.run_experiment --simulate
  ```
- *Live Gemini API Mode (via OpenRouter or Google GenAI):*
  ```bash
  python -m research.evaluation.run_experiment
  ```

**Step 4: Start the FastAPI Backend Server**
```bash
uvicorn backend.app.main:app --reload --port 8000
```
Interactive API documentation available at `http://127.0.0.1:8000/docs`.

---

## 9. Repository Structure

Suggested starting structure; it can be adjusted to the code generator and framework you choose.

```text
ceylix-ai/
├── README.md
├── .env.example
├── .gitignore
├── frontend/
│   ├── package.json
│   └── src/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── rules.py
│   │   ├── gemini_service.py
│   │   ├── evidence_validator.py
│   │   └── review_policy.py
│   ├── tests/
│   └── requirements.txt
├── research/
│   ├── data/
│   │   └── cases.json
│   ├── evaluation_protocol.md
│   └── results/
└── docs/
    ├── development_overview.md
    ├── architecture.md
    └── demo-script.md
```

Do not create empty placeholder modules and describe them as implemented. Keep tests and the research protocol aligned with the actual code.

## 10. Local Development

These are **illustrative setup commands**; adjust them to match the generated repository.

### Backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux**
```bash
source .venv/bin/activate
```

Install dependencies and start the API:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If the app is configured with FastAPI's default documentation route, visit `http://127.0.0.1:8000/docs`.

### Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Use the local URL printed by the frontend development server. These commands will work only after the corresponding files and scripts have been created.

## 11. Environment Variables

Create a local `.env` file from `.env.example`. Do not commit `.env`.

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=
GOOGLE_CLOUD_PROJECT=
FIRESTORE_COLLECTION=cases
```

Add Firebase and deployment configuration only where needed. Use the current official SDK and deployment documentation when configuring credentials. The frontend must never receive a privileged server-side API key.

## 12. Security and Reliability Requirements

- Validate and constrain incoming request sizes and data types.
- Keep secrets out of source control, logs, browser code, and demo screenshots.
- Treat case evidence as untrusted input; it must not override system instructions or validation rules.
- Separate model output from deterministic rule outcomes.
- Independently verify claim references and values against source records.
- Record source timestamps and define how stale evidence is identified.
- Fail safely when the model, database, or external data source is unavailable.
- Do not fabricate evidence or silently fill missing values.
- Display warnings and human-review requirements clearly.
- Minimize stored data and avoid logging sensitive information.
- Add authentication and access controls before exposing non-synthetic or sensitive cases.
- Make clear that risk flags are decision support, not proof of wrongdoing.

## 13. Team Responsibilities

For the planned three-person team:

- **Software engineer:** frontend, backend/API, Gemini integration, data schemas, claim validation, and cloud integration.
- **Cybersecurity intern 1:** literature review, synthetic dataset design, expected outcomes, evaluation protocol, and evidence-source documentation.
- **Cybersecurity intern 2:** test execution, security checks, failure-case testing, measurement records, deployment support, and demo/video coordination.

Coordinate through small Git issues or tasks. Require pull-request review for changes to rules, validation, secrets, or deployment configuration.

## 14. Competition Submission Checklist

Confirm the official competition rules and required format before submission. Track each item honestly.

- [ ] Confirm team eligibility, track, member limits, and submission deadline from official sources.
- [ ] Build a working public prototype.
- [ ] Demonstrate actual Gemini integration.
- [ ] Demonstrate Firestore integration if claimed.
- [ ] Deploy the frontend and backend to the intended hosting services, if required.
- [ ] Include a clear synthetic-data label and safety limitations.
- [ ] Run the baseline and validated workflows on the same test cases.
- [ ] Save test results and report measured values only.
- [ ] Verify that evidence IDs, values, conflicts, staleness, and abstention behave as expected.
- [ ] Test missing API credentials, API failures, invalid inputs, and database failures.
- [ ] Remove secrets, personal data, and debugging artifacts from the repository.
- [ ] Prepare the official pitch deck and a 3–4 minute demo video if those are the required formats.
- [ ] Test the public demo from a clean browser session.
- [ ] Verify every submission link before submitting.

## 15. Research Integrity

Ceylix AI's proposed contribution is an evaluated engineering approach to evidence quality, claim traceability, and abstention in a transaction-investigation workflow. Do not claim that LLM-based fraud investigation, deterministic verification, or abstention are entirely new ideas. Review related work, cite sources accurately, and state precisely what the implementation and experiment contribute.

Publish the test methodology and limitations with the results. Negative or mixed results are still useful if reported honestly.

## 16. Current Status

Update this section as real work is completed.

- [x] Requirements confirmed
- [x] Architecture implemented
- [x] Deterministic rules tested (7 transparent BFSI risk rules)
- [x] Gemini integration tested (OpenRouter & Google GenAI)
- [x] Claim validator tested (provenance, staleness, contradictions, prompt injection)
- [x] Synthetic dataset generator implemented (60 cases, 6 categories, seed=42)
- [x] External benchmark grounding (Kaggle creditcardfraud, IBM AMLSim, CFPB API)
- [x] Evaluation completed (Workflow A vs Workflow B empirical benchmark)
- [ ] Firestore integration tested
- [ ] Frontend connected to backend
- [ ] Deployment verified
- [ ] Demo and submission materials completed

## 17. Disclaimer

Ceylix AI is an experimental prototype for research and demonstration. It is not a production financial-crime system and must not be used as the sole basis for financial, legal, compliance, or customer-impacting decisions. All demo conclusions require appropriate human review.

---

**Built for AI Builder Cup 2026 by Team Ceylix AI.**
