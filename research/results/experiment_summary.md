# Ceylix AI Empirical Evaluation Report

## Controlled Synthetic Benchmark Evaluation

This document reports the empirical evaluation of Ceylix AI across **60 reproducible test cases** comparing:
- **Workflow A (Baseline):** Gemini without the validation layer
- **Workflow B (Validated):** Gemini with deterministic evidence validation and abstention

---

### Core Comparative Metrics

| Metric | Workflow A (Baseline) | Workflow B (Validated) | Delta / Improvement |
|---|---|---|---|
| **Unsupported-Claim Rate** | `43.3%` (26/60) | `0.0%` (0/59) | **-43.3% reduction** |
| **Correct Abstention Rate** | `0.0%` (0/40) | `100.0%` (40/40) | **+100.0% improvement** |
| **False Rejection Rate (FRR)** | `0.0%` (0/20) | `10.0%` (2/20) | `10.0%` (usable cases preserved) |
| **Evidence Traceability** | `83.3%` (50/60) | `83.1%` (49/59) | **+-0.3% verified provenance** |
| **Median Latency** | `50.0 ms` | `50.2 ms` | `+0.2 ms` validation overhead |
| **Mean Latency** | `50.0 ms` | `49.4 ms` | `+-0.6 ms` |
| **P95 Latency** | `50.0 ms` | `50.6 ms` | `+0.6 ms` |

---

### Category-Level Breakdown

| Category | Cases | Baseline Unsupported Rate | Validated Abstention Rate |
|---|---|---|---|
| **1. Complete & Consistent Evidence** | 10 | `0.0%` | `0.0%` |
| **2. Missing Evidence** | 10 | `100.0%` | `100.0%` |
| **3. Conflicting Evidence** | 10 | `20.0%` | `100.0%` |
| **4. Stale Evidence** | 10 | `40.0%` | `100.0%` |
| **5. Untrusted Instructions in Evidence** | 10 | `100.0%` | `100.0%` |
| **6. Benign and Suspicious Controls** | 10 | `0.0%` | `20.0%` |

---

### Key Findings

1. **Hypothesis H1 Confirmed:** The validation workflow reduced the unsupported-claim rate from **43.3%** in the unvalidated baseline down to **0.0%** by independently checking claimed fields, dates, and evidence IDs against source records.
2. **Hypothesis H2 Confirmed:** The validation workflow successfully abstained from releasing conclusions on **100.0%** of defective/insufficient evidence cases, whereas the unvalidated baseline abstained in only **0.0%** of such cases.
3. **Hypothesis H3 Confirmed (Measurable Trade-Off):** Deterministic claim-level validation adds a negligible latency overhead of approximately **0.2 ms** (median), while maintaining a **10.0% False Rejection Rate** on usable cases.

> **Disclaimer:** All benchmark scenarios use synthetic financial cases. Findings reflect algorithmic evidence validation properties and do not establish live production fraud detection rates.
