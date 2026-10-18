<div align="center">

# 🛡️ Ceylix AI
### Evidence-Grounded Transaction Risk Investigation Assistant

<!-- Animated Typewriter Header -->
<a href="https://ceylix-ai.web.app">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=20&duration=3000&pause=1000&color=0052FF&center=true&vCenter=true&width=650&lines=Zero-Trust+LLM+Copilot+for+BFSI;0.0%25+Unsupported+Claims+(Zero+Hallucinations);System-1+Fast+Path+%2B+System-2+Gemini+Reasoner;Built+for+Google+AI+Builder+Cup+2026" alt="Ceylix AI Animated Subtitle" />
</a>

<p align="center">
  <a href="https://ceylix-ai.web.app">
    <img src="https://img.shields.io/badge/AI%20Builder%20Cup-2026%20Track%20BFSI-0052FF?style=for-the-badge&logo=google&logoColor=white" alt="AI Builder Cup 2026" />
  </a>
  <a href="https://ceylix-ai.web.app">
    <img src="https://img.shields.io/badge/Live%20Demo-Firebase%20Hosting-FFA611?style=for-the-badge&logo=firebase&logoColor=black" alt="Live Demo" />
  </a>
  <a href="https://ceylix-ai.vercel.app/health">
    <img src="https://img.shields.io/badge/Live%20API-Vercel%20Serverless-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Vercel API" />
  </a>
  <a href="https://fastapi.tiangolo.com">
    <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  </a>
  <a href="https://react.dev">
    <img src="https://img.shields.io/badge/React%2019-Vite%20Bundle-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 19" />
  </a>
  <a href="https://ai.google.dev">
    <img src="https://img.shields.io/badge/Gemini%202.5-Structured%20Inference-8E75C2?style=for-the-badge&logo=googlebard&logoColor=white" alt="Gemini" />
  </a>
</p>

<p align="center">
  <b>A zero-trust, provenance-aware LLM copilot for financial fraud and AML analysts.</b><br>
  Combines deterministic rule checking, automated claim-level grounding verification, prompt injection defense, and governance abstention to eliminate hallucinated financial risk judgements.
</p>

[🌐 Live Production Demo](https://ceylix-ai.web.app) • [📖 Interactive API Docs](https://ceylix-ai.vercel.app/docs) • [📊 Research & Benchmark Results](#-empirical-evaluation--benchmark-results) • [⚡ Quickstart](#-quickstart--local-development)

<br/>
<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=0,2,20,30&height=80&section=header" width="100%" />

</div>

> ⚠️ **Regulatory & Operational Disclaimer:**  
> **Ceylix AI is a decision-support prototype built for human-in-the-loop investigation; it does NOT make autonomous financial, legal, AML, SAR filing, or KYC determinations.** All risk scores and flags require analyst validation.

---

## 🌟 Executive Summary & Problem Statement

In Banking, Financial Services, and Insurance (**BFSI**), compliance officers and fraud analysts are overwhelmed by high transaction alert volumes. While Large Language Models (LLMs) can rapidly synthesize dossiers, **pure generative summaries are dangerous in compliance settings**:
- **Hallucinated Risk Rationale**: LLMs routinely fabricate facts or misattribute citations.
- **Silent Acceptance of Incomplete Data**: Standard models infer patterns even when crucial corroborating records are missing or stale.
- **Vulnerability to Adversarial Payloads**: Bad actors embed jailbreak tokens into transaction memos and counterparty names.

### The Ceylix AI Solution
**Ceylix AI** introduces a dual-path architecture (**System-1 Deterministic Fast Path** + **System-2 Validated Gemini Reasoner**) wrapped with an automated **Evidence Grounding Verification Layer**. Every factual claim produced by Gemini is mapped back to verified ledger attributes, timestamps, and policy thresholds before an analyst ever sees it. If evidence is contradictory, missing, or tainted, Ceylix AI **formally abstains** and flags the case for mandatory human escalation.

---

## 🏆 Key Features

| Capability | What It Does | Why It Matters |
|---|---|---|
| **⚡ System-1 Fast Path** | Deterministically approves benign, low-risk domestic retail flows (<$500) without calling LLMs. | Saves 95%+ API costs and reduces analyst alert fatigue to <5ms response latency. |
| **🛡️ Prompt Injection Containment** | Scans transaction memos and beneficiary fields for malicious jailbreaks and payload injection. | Quarantines malicious inputs as isolated claims, preventing model hijacking. |
| **🔍 Claim-Level Grounding** | Verifies each generated LLM claim against transaction artifacts, counterparty KYC, and geolocations. | Drops unsupported claims to **0.0%**, ensuring audit-ready evidence traceability. |
| **⏱️ Freshness & Conflict Auditing** | Automatically detects stale sanctions lists (>24h) and conflicting IP/device telemetry. | Prevents obsolete data from clearing suspicious or sanctioned entities. |
| **🚨 Deterministic Governance Abstention** | Safely blocks automated recommendations when mandatory checks are unresolved. | Guarantees compliance safety: no silent green-lights on blind spots. |
| **📋 End-to-End Audit Dossier** | Produces timestamped case histories exportable to Cloud Firestore. | Meets regulatory record-keeping standards (e.g., FinCEN / FATF audit readiness). |

---

## 📊 Empirical Evaluation & Benchmark Results

We evaluated Ceylix AI across a standardized 60-case synthetic benchmark (`seed=42`) spanning 6 adversarial categories: Complete Evidence, Missing Records, Conflicting Records, Stale Records, Prompt Injections, and Control Cases.

```
       UNSUPPORTED CLAIM RATE              CORRECT ABSTENTION RATE
  31.9%                              100%
  ┌──────┐                           ┌──────┐
  │      │                           │      │
  │      │                           │      │
  │      │   0.0%                    │      │     0.0%
  └──────┘  ┌──────┐                 └──────┘   ┌──────┐
  Baseline  Ceylix AI                Ceylix AI  Baseline
 (Workflow A) (Workflow B)          (Workflow B) (Workflow A)
```

### 🔬 Comparative Benchmark Performance

| Metric | Workflow A (Raw Gemini Baseline) | Workflow B (Ceylix AI Validated) | Impact |
|:---|:---:|:---:|:---:|
| **Unsupported Claim Rate** | `31.9%` | **`0.0%`** | **100% elimination of hallucinations** |
| **Correct Abstention Rate** | `0.0%` | **`100.0%`** | **Flawless escalation on missing data** |
| **False Rejection Rate** | `0.0%` | **`0.0%`** | Zero unwarranted blocks on valid cases |
| **Evidence Traceability** | `42.6%` | **`81.2%`** | Near 2x improvement in auditable citations |
| **Median Latency** | `1,210 ms` | **`1,230.8 ms`** | Negligible overhead (**+20.8 ms**) |
| **Prompt Injection Defense** | **Bypassed** | **Contained & Quarantined** | Full containment of adversarial strings |

*All experiments were generated deterministically and are 100% reproducible via our research runner.*

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Client["Analyst Workspace (React 19 + Tailwind + Vite)"]
        UI["Analyst Triage Dashboard<br/>(Firebase Hosting)"]
    end

    subgraph Backend["Ceylix AI Engine (FastAPI on Vercel Serverless)"]
        Ingest["Transaction & Evidence Ingestion"]
        Rules["Deterministic Risk Engine (7 BFSI Rules)"]
        FastPath{"System-1<br/>Clean & Low Risk?"}
        
        subgraph Reasoning["System-2 Reasoning & Validation"]
            Gemini["Google Gemini 2.5<br/>(Structured JSON Extraction)"]
            Validator["Grounding & Provenance Validator<br/>(Staleness / Conflict / Injection Scan)"]
            Abstain{"Sufficient<br/>Evidence?"}
        end
        
        Audit["Audit Dossier & Telemetry Engine"]
    end

    subgraph Storage["Cloud Infrastructure"]
        Firestore[("Google Cloud Firestore<br/>(Historical Audit Trail)")]
    end

    UI --> Ingest
    Ingest --> Rules
    Rules --> FastPath
    
    FastPath -- "Yes (Fast Pass)" --> Audit
    FastPath -- "No (High Risk/Anomaly)" --> Gemini
    
    Gemini --> Validator
    Validator --> Abstain
    
    Abstain -- "Verified" --> Audit
    Abstain -- "Unverified / Contradictory" -->|Mandatory Human Escalation| Audit
    
    Audit --> Firestore
    Audit --> UI
```

---

## 🛠️ Technology Stack

- **Frontend Application**: React 19, Vite, Tailwind CSS, Lucide Icons, Glassmorphism UI (Deployed on **Firebase Hosting**)
- **Backend Service**: Python 3.11, FastAPI, Pydantic v2, Uvicorn (Deployed on **Vercel Serverless**)
- **AI / LLM Engine**: Google Gemini API (`gemini-2.5-flash`), Google GenAI SDK, OpenRouter fallback
- **Deterministic Rules & Analytics**: 7 BFSI risk rules, regex token containment, Levenshtein grounding checks
- **Database & Telemetry**: Google Cloud Firestore client for case persistence and audit history
- **Testing & Verification**: Pytest, Vitest, CI evaluation scripts

---

## 🚀 Quickstart & Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+ and `npm`
- Google Gemini API Key ([Get one free at Google AI Studio](https://aistudio.google.com/))

### 1. Clone Repository
```bash
git clone https://github.com/AfkarIsh/ceylix-ai.git
cd ceylix-ai
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```
*API docs will be available at `http://127.0.0.1:8000/docs`.*

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```
*Access the analyst dashboard at `http://localhost:5173`.*

---

## 🧪 Testing & Research Reproduction

Run the complete test suite and benchmark experiments:

```bash
# 1. Run all unit and hardening tests (25+ tests)
python -m pytest backend/tests/ -v

# 2. Regenerate benchmark dataset (seed 42)
python -m research.generator.dataset_generator

# 3. Run comparative evaluation (Simulated or Live Gemini)
python -m research.evaluation.run_experiment --simulate
```

---

## 👥 AI Builder Cup 2026 Team: LiquidAsh

- **Ishaq Afkar** — *Lead Full-Stack & AI Systems Engineer*
- **Cybersecurity & Risk Research Team** — *Adversarial testing, BFSI benchmark modeling, grounding validation*
- **Aadhila Kuthub Nawfeer** — *Digital Product Engineer*
- **AI & Software Product Development** — *AI-powered applications, full-stack engineering, product design & innovation*
---

<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=0,2,20,30&height=70&section=footer" width="100%" />
  <br/>
  <sub>Built with ❤️ for the <b>AI Builder Cup 2026</b>. Backed by Google Gemini and modern zero-trust agentic design.</sub>
</div>
