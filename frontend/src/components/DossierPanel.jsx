/**
 * DossierPanel.jsx — Panel 3: Findings & Evidence Dossier
 * ────────────────────────────────────────────────────────
 * Disposition header, regulatory narrative, verified evidence badges,
 * quarantined claims section, Firestore sync, and export button.
 *
 * Props:
 *   result              object  — investigation result
 *   caseId              string  — active case ID
 *   payload             object  — transaction payload (for export)
 *   backendStatus       string
 *   firestoreSyncState  'idle' | 'syncing' | 'success' | 'error'
 *   firestoreSyncTs     string | null — ISO timestamp of last successful sync
 *   onFirestoreSync     () => void
 *   onExportAudit       () => void
 */
import React, { useState } from 'react';
import {
  FileCheck,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Download,
  Cloud,
  Loader2,
  Lock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { DISPOSITION } from '../types.js';

// ─────────────────────────────────────────────────────────────────────────────
// Disposition header card — colour varies by disposition type
// ─────────────────────────────────────────────────────────────────────────────
function DispositionHeader({ disposition, isInvestigating, sarRecommendation, sarRationale }) {
  if (isInvestigating) {
    return (
      <div className="p-3.5 rounded-lg border bg-cyan-950/30 border-cyan-700/60 text-cyan-300 animate-pulse">
        <div className="text-[10px] uppercase font-bold tracking-widest opacity-70 mb-1">
          Forensic Triage In-Flight
        </div>
        <div className="text-sm font-bold font-mono tracking-wide flex items-center gap-2">
          <Loader2 className="w-4 h-4 text-cyan-400 animate-spin flex-shrink-0" />
          SYNTHESIZING REGULATORY DISPOSITION...
        </div>
        <div className="text-[10px] text-cyan-400/70 mt-1">
          Running deterministic evidence validator and Gemini 2.5 synthesis
        </div>
      </div>
    );
  }

  if (!disposition) {
    return (
      <div className="p-3.5 rounded-lg border bg-slate-900/60 border-slate-800 text-slate-400">
        <div className="text-[10px] uppercase font-bold tracking-widest opacity-70 mb-1">
          Disposition Status
        </div>
        <div className="text-sm font-bold font-mono tracking-wide text-slate-300">
          AWAITING INVESTIGATION
        </div>
        <div className="text-[10px] text-slate-500 mt-1">
          Execute triage to evaluate transaction telemetry against regulatory baselines
        </div>
      </div>
    );
  }

  if (disposition === DISPOSITION.DISMISS) {
    return (
      <div className="p-3.5 rounded-lg border bg-emerald-950/40 border-emerald-800/80 text-emerald-300 animate-fade-in">
        <div className="text-[10px] uppercase font-bold tracking-widest opacity-70 mb-1">
          Final Disposition Decision
        </div>
        <div className="text-sm font-bold font-mono tracking-wide flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          {disposition}
        </div>
        <div className="text-[10px] text-emerald-400/70 mt-1">
          Released with provenance · No regulatory action required
        </div>
      </div>
    );
  }

  if (disposition === DISPOSITION.EMERGENCY) {
    return (
      <div className="p-3.5 rounded-lg border bg-rose-950/50 border-rose-600/80 text-rose-300 animate-border-pulse animate-fade-in">
        <div className="text-[10px] uppercase font-bold tracking-widest opacity-70 mb-1">
          Final Disposition Decision
        </div>
        <div className="text-sm font-bold font-mono tracking-wide flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
          {disposition}
        </div>
        <div className="text-[10px] text-rose-400/70 mt-1">
          ⚠️ Transaction held · Security forensic review required immediately
        </div>
      </div>
    );
  }

  if (disposition === DISPOSITION.INPUT_MISMATCH) {
    return (
      <div className="p-3.5 rounded-lg border bg-amber-950/40 border-amber-700/80 text-amber-300 animate-fade-in">
        <div className="text-[10px] uppercase font-bold tracking-widest opacity-70 mb-1">
          Final Disposition Decision
        </div>
        <div className="text-sm font-bold font-mono tracking-wide flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
          {disposition}
        </div>
        <div className="text-[10px] text-amber-400/80 mt-1">
          Analyst Review Required · Non-payment instruction content detected · Suspicious financial activity not established
        </div>
      </div>
    );
  }

  // ESCALATE_FOR_ANALYST_REVIEW / Standard Analyst Review
  const isSarRecommended = Boolean(sarRecommendation);
  return (
    <div className="p-3.5 rounded-lg border bg-rose-950/40 border-rose-800/80 text-rose-300 animate-fade-in">
      <div className="flex items-center justify-between mb-1">
        <div className="text-[10px] uppercase font-bold tracking-widest opacity-70">
          Final Disposition Decision
        </div>
        <span className={`text-[9px] font-mono px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
          isSarRecommended
            ? "bg-rose-900/60 text-rose-200 border border-rose-600/60"
            : "bg-slate-800 text-slate-300 border border-slate-700"
        }`}>
          {isSarRecommended ? "SAR Referral: Recommended" : "SAR Referral: Not Established"}
        </span>
      </div>
      <div className="text-sm font-bold font-mono tracking-wide flex items-center gap-2">
        <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
        {disposition}
      </div>
      <div className="text-[10px] text-rose-400/80 mt-1">
        {isSarRecommended
          ? (sarRationale || "Mandatory compliance hold: Validated sanctions hit or structuring pattern identified.")
          : "Operational analyst review required before clearance. Suspicious financial crime not established on recorded baseline."}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Claim evidence binding row
// ─────────────────────────────────────────────────────────────────────────────
function ClaimRow({ claim }) {
  return (
    <div className="p-2.5 rounded bg-slate-900/80 border border-slate-800 text-xs animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-1 mb-1">
        <span className="font-mono text-[10px] text-cyan-300 font-bold bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/60">
          {claim.claim_id}
        </span>
        <span className="font-mono text-[10px] text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/60 flex items-center gap-1">
          <CheckCircle2 className="w-2.5 h-2.5 inline" />
          [{claim.tool}] → {claim.evidence_ref}
        </span>
      </div>
      <p className="text-[11px] text-slate-300 leading-snug">{claim.text}</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Quarantined claim row
// ─────────────────────────────────────────────────────────────────────────────
function QuarantinedClaimRow({ qc }) {
  return (
    <div className="p-2.5 bg-slate-950/90 rounded border border-rose-800/60 text-xs animate-fade-in">
      <div className="flex flex-wrap items-center gap-2 mb-1.5">
        <span className="font-mono text-[10px] text-rose-400 font-bold">
          [REDACTED BY GROUNDING GATE: UNVERIFIABLE ASSERTION]
        </span>
      </div>
      <div className="font-mono text-[9px] text-slate-500 mb-1.5">
        {qc.id} · Token: <span className="text-slate-400">{qc.source_token}</span>
      </div>
      <div className="text-rose-200 text-[11px] italic mb-1.5 leading-snug">
        "{qc.assertion}"
      </div>
      <div className="text-slate-500 text-[10px] leading-snug">
        <span className="font-semibold text-rose-400/80">Reason: </span>
        {qc.reason}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Firestore Sync Button
// ─────────────────────────────────────────────────────────────────────────────
function FirestoreSyncButton({ syncState, syncTs, onSync }) {
  if (syncState === 'syncing') {
    return (
      <button disabled className="flex-1 py-2 px-3 bg-slate-800 border border-slate-700 text-slate-400 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 cursor-not-allowed">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Syncing to Firestore…
      </button>
    );
  }

  if (syncState === 'success' && syncTs) {
    return (
      <div className="flex-1 py-2 px-3 bg-emerald-950/30 border border-emerald-800/60 rounded-lg flex flex-col items-center gap-0.5">
        <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-semibold">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Synced to Firestore
        </div>
        <div className="font-mono text-[9px] text-emerald-400/60">{syncTs}</div>
      </div>
    );
  }

  if (syncState === 'error') {
    return (
      <button
        onClick={onSync}
        className="flex-1 py-2 px-3 bg-amber-950/30 border border-amber-800/60 text-amber-300 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 hover:bg-amber-950/50 transition-colors"
      >
        <XCircle className="w-3.5 h-3.5" />
        Retry Firestore Sync
      </button>
    );
  }

  return (
    <button
      onClick={onSync}
      className="flex-1 py-2 px-3 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 hover:border-slate-600 text-slate-200 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-2"
      title="Persist this dossier to Cloud Firestore"
    >
      <Cloud className="w-3.5 h-3.5 text-cyan-400" />
      Sync to Cloud Firestore
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export default function DossierPanel({
  result,
  isInvestigating = false,
  caseId,
  payload,
  backendStatus,
  firestoreSyncState,
  firestoreSyncTs,
  onFirestoreSync,
  onExportAudit,
}) {
  const [narrativeExpanded, setNarrativeExpanded] = useState(true);

  const disposition = result?.disposition_title;
  const claims = Array.isArray(result?.claims) ? result.claims : [];
  const quarantinedClaims = Array.isArray(result?.quarantined_claims) ? result.quarantined_claims : [];
  const summary = result?.summary || (isInvestigating ? 'Synthesizing evidence claims with Gemini reasoning model...' : 'Awaiting investigation run...');
  const isInjectionScenario =
    disposition === DISPOSITION.EMERGENCY ||
    quarantinedClaims.length > 0;
  const workflowType = result?.workflow_type === 'validated_deterministic' ? 'Validated' : (result?.workflow_type ? 'Baseline' : 'Standby');
  const riskLevel = result?.preliminary_risk_level || (isInvestigating ? 'ANALYZING' : 'PENDING');

  return (
    <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col shadow-xl">

      {/* ── Panel Header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-3.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-cyan-400 flex-shrink-0" />
          <h2 className="text-xs font-bold tracking-widest text-slate-200 uppercase">
            Panel 3 · Findings & Evidence Dossier
          </h2>
        </div>
        <span className="text-[10px] font-mono text-slate-500 bg-slate-950/60 border border-slate-800 px-2 py-0.5 rounded">
          {caseId}
        </span>
      </div>

      {/* ── Scrollable Body ───────────────────────────────────────── */}
      <div className="mt-4 space-y-3.5 flex-1 overflow-y-auto max-h-[640px] pr-0.5">

        {/* Disposition Header */}
        <DispositionHeader
          disposition={disposition}
          isInvestigating={isInvestigating}
          sarRecommendation={result?.sar_recommendation}
          sarRationale={result?.sar_rationale}
        />

        {/* Injection Alert Banner for Scenario C */}
        {isInjectionScenario && disposition === DISPOSITION.EMERGENCY && (
          <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-700/60 flex items-start gap-2.5 animate-fade-in">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-[11px] font-bold text-rose-300 mb-0.5">
                ⚠️ ADVERSARIAL INJECTION BLOCKED — Ceylix Deterministic AST Gate Active
              </div>
              <p className="text-[10px] text-rose-400/70 leading-snug">
                All coerced LLM output was intercepted before regulatory dossier inclusion. Evidence below reflects deterministic findings only.
              </p>
            </div>
          </div>
        )}

        {/* Draft Regulatory Narrative */}
        <div className="p-3.5 bg-slate-950/80 rounded-lg border border-slate-800">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">
              Draft Regulatory Narrative
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-cyan-400 font-mono">Gemini Synthesis</span>
              <button
                onClick={() => setNarrativeExpanded(!narrativeExpanded)}
                className="text-slate-500 hover:text-slate-300 transition-colors"
              >
                {narrativeExpanded
                  ? <ChevronUp className="w-3.5 h-3.5" />
                  : <ChevronDown className="w-3.5 h-3.5" />
                }
              </button>
            </div>
          </div>
          {narrativeExpanded && (
            <div className="space-y-2 mt-1">
              <p className={`text-[11px] leading-relaxed animate-fade-in ${isInvestigating ? 'text-slate-500 italic' : 'text-slate-300'}`}>
                {summary}
              </p>

              {/* Structured Regulatory Indicators */}
              {!isInvestigating && result && (
                <div className="mt-2.5 pt-2 border-t border-slate-800/80 space-y-2">
                  {/* 1. Factual Indicators */}
                  <div className="text-[10px] bg-slate-900/60 p-2 rounded border border-slate-800/60">
                    <span className="font-bold text-slate-400 uppercase tracking-wide block mb-0.5">
                      Factual Indicators:
                    </span>
                    <span className="text-slate-300">
                      Amount: {payload?.currency || 'USD'} {Number(payload?.amount || 0).toLocaleString()} · Corridor: {payload?.origin_country || 'US'} → {payload?.counterparty_country || payload?.destination_country || 'US'} · Beneficiary: {payload?.counterparty_name || 'N/A'} · Settlement Bank: {payload?.counterparty_bank || 'N/A'}
                    </span>
                  </div>

                  {/* 2. Unresolved Questions */}
                  {(result.warnings?.length > 0 || result.probes?.ip_geo?.status === 'MATCHED' || (result.input_intent && result.input_intent !== 'PAYMENT_INSTRUCTION')) && (
                    <div className="text-[10px] bg-amber-950/20 p-2 rounded border border-amber-900/40">
                      <span className="font-bold text-amber-400 uppercase tracking-wide block mb-0.5">
                        Unresolved Questions:
                      </span>
                      <ul className="list-disc list-inside text-amber-200/80 space-y-0.5">
                        {result.probes?.ip_geo?.status === 'MATCHED' && (
                          <li>Proxy/VPN routing detected on client IP — physical geolocation obscured.</li>
                        )}
                        {result.input_intent && result.input_intent !== 'PAYMENT_INSTRUCTION' && (
                          <li>Payment memo contains unrelated non-financial text ({result.input_intent}) requiring verification.</li>
                        )}
                        {result.warnings?.map((w, idx) => (
                          <li key={idx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 3. Reason for Analyst Review */}
                  {result.decision === 'ABSTAIN_FOR_HUMAN_REVIEW' && (
                    <div className="text-[10px] bg-cyan-950/20 p-2 rounded border border-cyan-900/40">
                      <span className="font-bold text-cyan-400 uppercase tracking-wide block mb-0.5">
                        Reason for Analyst Review:
                      </span>
                      <span className="text-cyan-200/90">
                        {result.preliminary_risk_level === 'HIGH'
                          ? 'Mandatory sanctions & high-risk corridor review required before transaction release. Input mismatch quarantined.'
                          : 'Automated clearance withheld: non-payment instructions detected in memo. Refer to specialized operational workflow.'}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Novel-Threat Multivariate Anomaly Indicator (Phase 8) */}
        {!isInvestigating && result && result.anomaly_score != null && (
          <div className="p-3.5 bg-slate-950/80 rounded-lg border border-slate-800 text-slate-300 animate-fade-in">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                Novel-Threat Multivariate Anomaly Indicator
              </span>
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                result.anomaly_score >= 0.65
                  ? "bg-amber-950/60 text-amber-300 border border-amber-700/60"
                  : "bg-slate-900 text-emerald-400 border border-emerald-800/60"
              }`}>
                Anomaly: {(result.anomaly_score * 100).toFixed(1)}/100
              </span>
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              {result.anomaly_details?.explanation || (result.anomaly_score >= 0.65 ? "Statistical outlier detected relative to multidimensional customer baseline." : "Transaction conforms to expected multidimensional baseline.")}
            </p>
            {result.anomaly_details?.feature_contributions && (
              <div className="mt-2 grid grid-cols-2 gap-1.5 text-[9px] font-mono">
                {Object.entries(result.anomaly_details.feature_contributions).map(([feat, score]) => (
                  <div key={feat} className="bg-slate-900/80 px-2 py-1 rounded border border-slate-800 flex justify-between">
                    <span className="text-slate-400">{feat.replace('_', ' ')}</span>
                    <span className={score >= 0.5 ? "text-amber-400 font-bold" : "text-slate-300"}>
                      {(score * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="text-[9px] text-slate-500 italic mt-1.5 border-t border-slate-800/60 pt-1">
              Notice: Independent anomaly score measures statistical distance; does not independently trigger a SAR.
            </div>
          </div>
        )}

        {/* Verified Evidence Bindings */}
        <div className="p-3.5 bg-slate-950/80 rounded-lg border border-slate-800">

          <div className="flex items-center gap-2 text-[10px] uppercase font-semibold text-slate-500 tracking-wider mb-2.5">
            {isInvestigating ? (
              <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            )}
            Verified Evidence Bindings ({claims.length})
          </div>
          {claims.length > 0 ? (
            <div className="space-y-2">
              {claims.map((claim) => (
                <ClaimRow key={claim.claim_id} claim={claim} />
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-slate-500 italic">
              {isInvestigating
                ? 'Validating telemetry and generating grounded claims...'
                : 'No verified evidence claims generated yet.'}
            </p>
          )}
        </div>

        {/* Quarantined Claims Section — The Winning Differentiator */}
        {quarantinedClaims.length > 0 && (
          <div className="p-3.5 bg-rose-950/20 rounded-lg border border-rose-800/60 animate-fade-in">
            <div className="flex items-center gap-2 text-rose-400 text-[11px] font-bold uppercase tracking-wider mb-2">
              <Lock className="w-3.5 h-3.5 flex-shrink-0" />
              <span>Grounding Gate — Quarantined Claims ({quarantinedClaims.length})</span>
            </div>
            <p className="text-[10px] text-rose-300/80 mb-3 leading-snug">
              The following assertions were removed from this regulatory dossier because they failed deterministic validation or originated from adversarial injection tokens:
            </p>
            <div className="space-y-2">
              {quarantinedClaims.map((qc) => (
                <QuarantinedClaimRow key={qc.id} qc={qc} />
              ))}
            </div>
          </div>
        )}

        {/* Compliance Metadata */}
        <div className="p-3 bg-slate-950/50 rounded-lg border border-slate-800/50">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-[9px] uppercase font-semibold text-slate-600 tracking-wider">Workflow</div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                {workflowType}
              </div>
            </div>
            <div>
              <div className="text-[9px] uppercase font-semibold text-slate-600 tracking-wider">Risk Level</div>
              <div className={`text-[10px] font-mono font-bold mt-0.5 ${
                riskLevel === 'LOW'    ? 'text-emerald-400' :
                riskLevel === 'MEDIUM' ? 'text-amber-400'   :
                riskLevel === 'HIGH' || riskLevel === 'CRITICAL' ? 'text-rose-400' : 'text-slate-400'
              }`}>
                {riskLevel}
              </div>
            </div>
            <div>
              <div className="text-[9px] uppercase font-semibold text-slate-600 tracking-wider">Claims</div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                {claims.length} verified
                {quarantinedClaims.length > 0
                  ? ` · ${quarantinedClaims.length} quarantined`
                  : ''}
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* ── Action Footer ─────────────────────────────────────────── */}
      <div className="mt-4 pt-4 border-t border-slate-800 space-y-2">
        <div className="flex gap-2">
          <FirestoreSyncButton
            syncState={firestoreSyncState}
            syncTs={firestoreSyncTs}
            onSync={onFirestoreSync}
          />
          <button
            onClick={onExportAudit}
            className="py-2 px-3 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 hover:border-slate-600 text-slate-200 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1.5 flex-shrink-0"
            title="Download audit JSON"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span className="hidden sm:inline">Export JSON</span>
          </button>
        </div>
        <div className="text-[9px] text-slate-600 text-center font-mono">
          SYNTHETIC BENCHMARK CASE — NOT REAL FINANCIAL RECORDS · ISO 42001 Compliant
        </div>
      </div>
    </section>
  );
}
