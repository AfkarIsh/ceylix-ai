# Ceylix AI Research and Engineering Hardening

Status: engineering traceability record, not a certification or compliance
attestation. The controls below are implemented and tested only within the
synthetic benchmark and mocked-provider boundaries described here.

## 1. Source register

| Source | Issuer | Date | Access | Classification | Content reviewed |
|---|---|---|---|---|---|
| [Generative AI Profile, NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) | NIST | July 25, 2024 approval | REVIEWED | Voluntary framework | Confabulation and information-integrity risks (§2.2, §2.8); governance, measurement, provenance, testing, incident and feedback practices (GV-4.1 through GV-4.3). |
| [A Framework for OFAC Compliance Commitments](https://ofac.treasury.gov/recent-actions/20190502_33) | U.S. Treasury OFAC | Date not stated in reviewed page; linked document metadata last modified March 22, 2023 | REVIEWED | Official compliance guidance; applicable legal obligations depend on jurisdiction and facts | Risk-based sanctions program components: management commitment, risk assessment, internal controls, testing/auditing, and training; governance and resourcing. |
| [FATF risk-based guidance](https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Risk-based-approach-banking-sector.html) | FATF | Not established | NOT REVIEWED | Not classified from inaccessible source | Official endpoint returned HTTP 403. No FATF principle is asserted here. |
| [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | OWASP Foundation | Page date not displayed | REVIEWED | Voluntary engineering/security guidance | Project scope and stated focus on critical security vulnerabilities in LLM applications. Individual controls were not attributed beyond the accessible page. |
| [Vertex AI generative AI evaluation documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluate-models) | Google Cloud | Page date not displayed | REVIEWED | Engineering/product documentation | Prompt/ground-truth evaluation pairs, task metrics, dataset preparation, and repeated evaluation; this is not legal screening evidence. |
| [FFIEC BSA/AML Examination Manual](https://bsaaml.ffiec.gov/manual) | FFIEC | Not established | NOT REVIEWED | Not classified from inaccessible source | Official endpoint returned access denial/CAPTCHA. No FFIEC principle is asserted here. |

## 2. Research-to-code traceability

| Source principle | Ceylix component | Current implementation and gap | Remediation | Regression test and actual result |
|---|---|---|---|---|
| NIST: reduce confabulation and preserve information integrity | `backend/app/evidence_validator.py`, `backend/app/workflows.py` | Claims are checked for evidence IDs, ownership, staleness, contradictions, semantic support, and injection echoes. Previously, rejected claims were not exposed as a structured response collection. | Added `ValidationReport.quarantined_evidence` and `InvestigationReport.quarantined_evidence`; invalid claims and foreign records are explicitly quarantined. | `test_unsupported_claim_is_quarantined_and_grounding_is_not_full`, `test_report_exposes_quarantined_claims`; full backend suite: **73 passed**. |
| NIST: lifecycle traceability and cross-case integrity | `evidence_validator.py`, `intent_and_telemetry.py`, `workflows.py` | Evidence IDs could be present while records were bound to another transaction/customer; telemetry selection could reuse a foreign record. | Enforced explicit transaction/customer ownership when selecting screening, IP, and KYC records; retained case binding checks; reused non-benchmark case IDs are fingerprint-protected. | `test_foreign_evidence_is_rejected_even_when_id_is_present`, `test_telemetry_does_not_reuse_foreign_transaction_record`, `test_reused_case_id_with_changed_transaction_is_rejected`; **passed**. |
| OFAC: risk-based screening with internal controls and testing | `evidence_validator.py`, `rules.py`, `intent_and_telemetry.py` | Jurisdiction risk and entity sanctions status were previously vulnerable to semantic conflation; missing providers needed an explicit unavailable state. | Entity matches require exact normalized name/account, source record, and list/source reference. Missing screening becomes `UNKNOWN`/`DATA_UNAVAILABLE`; corridor and bank risk remain separate. | `test_high_risk_corridor_without_entity_evidence_is_not_confirmed_match`, `test_confirmed_match_requires_bound_source_and_exact_entity_attributes`, `test_partial_name_does_not_become_confirmed_match`, `test_us_corridor_and_tehran_bank_remain_separate_dimensions`; **passed**. |
| Google Cloud: evaluate against prompt/ground-truth pairs and repeat regressions | `backend/tests/` | Existing tests covered many scenarios but did not explicitly prove the new fast-path injection boundary or foreign telemetry reuse. | Added deterministic regression tests for those boundaries and ran the complete suite without relying on live model success. | Full backend suite: **73 passed**. Live Gemini/OpenRouter availability is not treated as a test result. |
| OWASP project scope: explicitly address LLM application threats | `backend/app/intent_and_telemetry.py`, `evidence_validator.py`, `workflows.py` | Untrusted memo/beneficiary instructions could reach the fast path before injection detection. | Fast path now requires no detected injection and no high-risk transaction signal; injection is routed through validation and quarantine. | `test_fast_path_does_not_bypass_prompt_injection`; **passed**. |
| FATF guidance | All AML-related components | NOT REVIEWED because the official endpoint returned 403. | No requirement is claimed or implemented as FATF-derived until the source is accessible and reviewed. | No FATF-specific test claimed. |
| FFIEC manual | All BSA/AML components | NOT REVIEWED because the official endpoint required blocked access/CAPTCHA. | No requirement is claimed or implemented as FFIEC-derived until the source is accessible and reviewed. | No FFIEC-specific test claimed. |

## 3. Updated technical requirements

1. A case, transaction, customer, beneficiary, bank, and IP observation are
   separate identities. Evidence with an explicit owner must match that owner.
2. `CONFIRMED_MATCH` requires exact entity or account matching plus a traceable
   source/list reference. Country, bank location, substring similarity, or an
   unavailable provider cannot establish an entity match.
3. Missing screening is observable as `UNKNOWN` or `DATA_UNAVAILABLE`, never a
   fabricated clear or match.
4. Every material model claim must cite existing same-case evidence and
   semantically agree with it. Unsupported, stale, conflicting, foreign, or
   injection-derived claims are quarantined and cannot establish disposition.
5. The fast path is allowed only for low-value domestic commercial payments with
   no injection and no high-risk transaction signal.
6. Risk dimensions remain distinct: sanctions exposure, corridor, bank,
   device/network, KYC, velocity, and data quality. A score is not a sanctions
   finding and a threshold is not proof of criminality.
7. A live-provider failure, quota error, or unavailable source must be visible
   as unavailable/fallback behavior; synthetic fixtures and deterministic
   fallbacks must not be represented as live screening.

## 4. Threat model and data-flow review

| Threat | Trust boundary | Control | Residual limitation |
|---|---|---|---|
| Prompt injection in memo/beneficiary | User input -> parser/workflow | Injection detection, fast-path exclusion, claim quarantine, intent routing | Pattern-based detection is not a complete semantic detector. |
| Cross-case evidence contamination | Request/evidence bundle -> validators | Explicit case, transaction, and customer binding; case fingerprint reuse protection | In-memory fingerprint state is process-local and not durable across restarts. |
| Fabricated sanctions match | Provider/fixture -> sanctions rule | Exact entity/account match, source/list reference, unavailable state | No live provider was verified in this run. |
| Unsupported narrative | Model output -> report | Evidence ID, ownership, freshness, contradiction, semantic and field-reference validation | Model fallback is deterministic but still requires review when evidence is incomplete. |
| Risk-score inconsistency | Rules -> policy/report/frontend | Authoritative deterministic score and dimensions are emitted in the report | No independent production score service or immutable audit store is configured. |
| Persistence loss | Browser/backend -> history/audit | Local history and backend sync paths exist | Browser local storage is not a regulated durable audit record. |

## 5. Risk-scoring and grounding specification

- `risk_score` and `calibrated_score` are deterministic policy outputs from
  structured transaction/rule inputs; `anomaly_score` is a separate
  experimental signal and must not be interpreted as a sanctions result.
- `HIGH_RISK_JURISDICTION` contributes corridor risk only.
- `SanctionsWatchlistRule` is flagged only for usable entity-level evidence.
- VPN/proxy, amount thresholds, or high-risk corridors do not independently
  establish fraud, money laundering, or SAR obligation.
- `FULLY_GROUNDED` requires all claims to be supported and traceable with no
  injection, unsupported/conflicting/stale defects, or missing mandatory
  evidence. Fast-path reports are deterministic and contain no model claims.
- `PARTIALLY_GROUNDED` indicates stale/missing evidence without unsupported or
  conflicting claims. `UNGROUNDED` indicates an integrity defect requiring
  review.

## 6. Actual verification report

- Backend: `pytest -q` in `backend/` -> **73 passed in 94.56s**.
- New integrity regressions: **11 passed** in
  `backend/tests/test_evidence_integrity_repair.py`.
- Frontend: `npm run build` in `frontend/` -> **passed**, Vite production bundle
  generated successfully.
- Live Gemini/OpenRouter calls: **not used as pass criteria**; prior runs
  encountered provider quota/credit limits.
- FATF and FFIEC: **not reviewed**, so no compliance conclusion is drawn.

## 7. Remaining-defects register

| Severity | Defect | Impact | Next control |
|---|---|---|---|
| HIGH | Case fingerprint protection is in-memory and process-local. | A restart can lose reuse detection; multi-worker deployments do not share the fingerprint map. | Persist canonical input hashes in a transactional store keyed by case ID and reject conflicting updates atomically. |
| HIGH | Screening and evidence sources are synthetic, mocked, or unavailable in the test environment. | The suite proves semantics, not live sanctions-provider accuracy or coverage. | Integrate an approved provider in a controlled environment and test source freshness, outages, and audit records. |
| MEDIUM | Injection detection is regex/pattern-based. | Novel obfuscated instructions may evade detection. | Add adversarial corpus evaluation and independent classifier/rule review without allowing model output to override deterministic policy. |
| MEDIUM | Browser local storage is not a durable compliance audit trail. | Clearing browser state or device loss can remove local history. | Use authenticated server-side append-only persistence with access controls and retention policy. |
| MEDIUM | FATF and FFIEC source content remains unavailable. | Those deliverables cannot be mapped or used as evidence. | Review the official documents manually or through an approved accessible source, then add verified mappings/tests. |
| LOW | Fast-path latency is measured in-process, not under network/deployment load. | The value is not a production SLA measurement. | Benchmark a deployed service with representative concurrency and record p50/p95/p99. |

## 8. Readiness recommendation

Ceylix AI is suitable for continued synthetic benchmark evaluation and
engineering demonstrations after the verified test run. It is **not** shown to
be legally compliant, production-ready for regulated decisions, or validated
against live sanctions providers. Address durable cross-worker case
fingerprints, authenticated audit persistence, live provider controls, and the
unreviewed FATF/FFIEC sources before making a production or regulatory
readiness claim.
