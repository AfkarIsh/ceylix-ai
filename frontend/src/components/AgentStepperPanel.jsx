/**
 * AgentStepperPanel.jsx — Panel 2: Agent Execution Stepper
 * ──────────────────────────────────────────────────────────
 * Live 4-stage progress tracker with animated risk gauge, probe chips,
 * grounding status, and measured roundtrip latency display.
 *
 * Props:
 *   result           object  — live investigation result from FastAPI backend
 *   lastExecutionTime string  — e.g. "2,840 ms"
 *   isInvestigating  boolean — whether a triage is currently in flight
 *   backendStatus    string
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Layers,
  ShieldAlert,
  Globe,
  Database,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  Cpu,
  Activity,
  Zap,
  Loader2,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Risk Gauge — animated horizontal bar with color transitions
// ─────────────────────────────────────────────────────────────────────────────
function RiskGauge({ score, riskLevel }) {
  const [displayScore, setDisplayScore] = useState(0);
  const [rendered, setRendered]         = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    setRendered(false);
    setDisplayScore(0);
    // brief delay so CSS transition triggers fresh
    timerRef.current = setTimeout(() => {
      setRendered(true);
      // animate counter
      const start    = performance.now();
      const duration = 900;
      const step = (now) => {
        const elapsed  = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased    = 1 - Math.pow(1 - progress, 3); // cubic ease-out
        setDisplayScore(Math.round(eased * score));
        if (progress < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }, 80);
    return () => clearTimeout(timerRef.current);
  }, [score]);

  const pct = Math.max(0, Math.min(100, score));

  // Authoritative risk level mapping: 0-29 LOW, 30-69 MEDIUM, 70-100 HIGH
  const derivedLevel = riskLevel || (pct >= 70 ? 'HIGH' : pct >= 30 ? 'MEDIUM' : 'LOW');
  let barColor, textColor, label;
  if (derivedLevel === 'HIGH' || pct >= 70) {
    barColor  = 'from-rose-600 to-rose-800';
    textColor = 'text-rose-400';
    label     = 'HIGH';
  } else if (derivedLevel === 'MEDIUM' || pct >= 30) {
    barColor  = 'from-amber-500 to-amber-700';
    textColor = 'text-amber-400';
    label     = 'MEDIUM';
  } else {
    barColor  = 'from-emerald-500 to-emerald-700';
    textColor = 'text-emerald-400';
    label     = 'LOW';
  }

  return (
    <div className="mt-3">
      <div className="flex items-end justify-between mb-1.5">
        <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">
          Calibrated Risk Score
        </div>
        <div className="flex items-baseline gap-1">
          <span className={`text-2xl font-bold font-mono ${textColor}`}>
            {displayScore}
          </span>
          <span className="text-xs text-slate-500 font-mono">/100</span>
          <span className={`text-[10px] font-bold ml-1.5 px-1.5 py-0.5 rounded border font-mono ${
            derivedLevel === 'HIGH' || pct >= 70 ? 'text-rose-400 bg-rose-950/40 border-rose-800/60' :
            derivedLevel === 'MEDIUM' || pct >= 30 ? 'text-amber-400 bg-amber-950/40 border-amber-800/60' :
                        'text-emerald-400 bg-emerald-950/40 border-emerald-800/60'
          }`}>
            {label}
          </span>
        </div>
      </div>

      {/* Track */}
      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
        {/* Fill */}
        <div
          className={`h-full rounded-full bg-gradient-to-r ${barColor} gauge-bar`}
          style={{ '--gauge-target': `${pct}%`, width: rendered ? `${pct}%` : '0%', transition: 'width 0.9s cubic-bezier(0.4,0,0.2,1)' }}
        />
      </div>

      {/* Tick marks */}
      <div className="flex justify-between mt-0.5 text-[9px] font-mono text-slate-700">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Probe Status Chip
// ─────────────────────────────────────────────────────────────────────────────
function ProbeChip({ status, sourceLabel }) {
  const badge = (() => {
    switch (status) {
      case 'CLEAR':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-emerald-400 bg-emerald-950/40 border-emerald-800/80 flex-shrink-0">
            CLEAR
          </span>
        );
      case 'MATCHED':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-rose-400 bg-rose-950/40 border-rose-800/80 flex-shrink-0">
            MATCHED
          </span>
        );
      case 'RUNNING':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-cyan-400 bg-cyan-950/40 border-cyan-800/80 flex-shrink-0 flex items-center gap-1">
            <Loader2 className="w-2.5 h-2.5 animate-spin" />
            RUNNING
          </span>
        );
      case 'DATA_UNAVAILABLE':
      case 'UNAVAILABLE':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-amber-400 bg-amber-950/40 border-amber-800/80 flex-shrink-0">
            UNAVAILABLE
          </span>
        );
      case 'SIMULATED':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-indigo-400 bg-indigo-950/40 border-indigo-800/80 flex-shrink-0">
            SIMULATED
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-slate-400 bg-slate-900 border-slate-800 flex-shrink-0">
            {status || 'UNKNOWN'}
          </span>
        );
    }
  })();

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0">
      {sourceLabel && (
        <span className="text-[8px] font-mono text-slate-500 bg-slate-900/80 border border-slate-800/80 px-1 py-0.5 rounded hidden sm:inline" title={sourceLabel}>
          {sourceLabel.includes("Live") ? "LIVE EXT" : "LOCAL RULE"}
        </span>
      )}
      {badge}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Grounding Status Badge
// ─────────────────────────────────────────────────────────────────────────────
function GroundingBadge({ status }) {
  switch (status) {
    case 'FULLY_GROUNDED':
      return (
        <span className="inline-flex items-center gap-1.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-emerald-400 bg-emerald-950/40 border-emerald-800/80">
          <CheckCircle2 className="w-3 h-3" />
          FULLY_GROUNDED
        </span>
      );
    case 'PARTIALLY_GROUNDED':
      return (
        <span className="inline-flex items-center gap-1.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-amber-400 bg-amber-950/40 border-amber-800/80">
          <AlertCircle className="w-3 h-3" />
          PARTIALLY_GROUNDED
        </span>
      );
    case 'BLOCKED':
    case 'BLOCKED_UNVERIFIED_CLAIMS':
      return (
        <span className="inline-flex items-center gap-1.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded border text-rose-400 bg-rose-950/40 border-rose-800/80">
          <XCircle className="w-3 h-3" />
          {status}
        </span>
      );
    default:
      return (
        <span className="text-[10px] font-mono text-slate-400">{status || 'PENDING'}</span>
      );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step Number Badge
// ─────────────────────────────────────────────────────────────────────────────
function StepBadge({ n }) {
  return (
    <span className="w-5 h-5 rounded-full bg-cyan-950 border border-cyan-500/50 text-[10px] font-bold text-cyan-300 flex items-center justify-center flex-shrink-0">
      {n}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export default function AgentStepperPanel({
  result,
  lastExecutionTime,
  isInvestigating,
  backendStatus,
}) {
  const latencyMs = result?.latency_ms != null ? result.latency_ms : null;
  const latencyS = latencyMs != null ? (latencyMs / 1000).toFixed(2) : null;

  const system1Model = result?.system1_model || (isInvestigating ? 'gemini-3.8-flash (Reflex)' : 'gemini-3.8-flash');
  const system1Disposition = result?.system1_disposition || (isInvestigating ? 'EVALUATING' : 'STANDBY');
  const score = result?.calibrated_score ?? 0;

  const ofacProbe = result?.probes?.ofac_sdn || {
    status: isInvestigating ? 'RUNNING' : 'DATA_UNAVAILABLE',
    detail: isInvestigating ? 'Validating against OFAC SDN & consolidated sanctions...' : 'Awaiting investigation run',
  };
  const ipGeoProbe = result?.probes?.ip_geo || {
    status: isInvestigating ? 'RUNNING' : 'DATA_UNAVAILABLE',
    detail: isInvestigating ? 'Inspecting IP geolocation, ASN & proxy headers...' : 'Awaiting investigation run',
  };
  const coreKycProbe = result?.probes?.core_kyc || {
    status: isInvestigating ? 'RUNNING' : 'DATA_UNAVAILABLE',
    detail: isInvestigating ? 'Comparing transaction velocity with core KYC baseline...' : 'Awaiting investigation run',
  };

  const system2Model = result?.system2_model || (isInvestigating ? 'gemini-3.8-flash (Synthesis)' : 'gemini-3.8-flash');
  const quarantinedCount = result?.quarantined_claims?.length || 0;

  return (
    <section className={`bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col shadow-xl relative ${isInvestigating ? 'scan-line overflow-hidden' : ''}`}>

      {/* ── Panel Header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-3.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-400 flex-shrink-0" />
          <h2 className="text-xs font-bold tracking-widest text-slate-200 uppercase">
            Panel 2 · Agent Execution Stepper
          </h2>
        </div>
        <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/40 border border-cyan-800/60 px-2 py-0.5 rounded flex-shrink-0">
          ⏱ {lastExecutionTime}
        </span>
      </div>

      <div className="mt-4 space-y-3 flex-1">

        {/* ─── STEP 1: System 1 Reflex ─────────────────────────────── */}
        <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800 step-connector animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <StepBadge n={1} />
              <div>
                <span className="text-xs font-semibold text-slate-200">System 1 Reflex</span>
                <div className="text-[10px] text-slate-500 mt-0.5">Fast triage · sub-200ms target</div>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                {system1Model}
              </span>
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                system1Disposition === 'PASS'
                  ? 'text-emerald-400 bg-emerald-950/40 border-emerald-800/80'
                  : system1Disposition === 'FLAG' || system1Disposition === 'ESCALATE' || system1Disposition === 'DISPATCH_INVESTIGATION'
                  ? 'text-amber-400 bg-amber-950/40 border-amber-800/80'
                  : 'text-slate-400 bg-slate-900 border-slate-800'
              }`}>
                {system1Disposition}
              </span>
            </div>
          </div>

          {/* Risk Gauge */}
          {isInvestigating ? (
            <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
              <span>Computing triage score…</span>
            </div>
          ) : !result ? (
            <div className="mt-3 text-[11px] text-slate-500 font-mono">
              <span>Awaiting investigation score…</span>
            </div>
          ) : (
            <RiskGauge score={score} riskLevel={result?.preliminary_risk_level} />
          )}
        </div>

        {/* ─── STEP 2: Parallel Telemetry Probes ───────────────────── */}
        <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800 step-connector animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <StepBadge n={2} />
              <div>
                <span className="text-xs font-semibold text-slate-200">Parallel Telemetry Mesh</span>
                <div className="text-[10px] text-slate-500 mt-0.5">Deterministic rule engine</div>
              </div>
            </div>
            <span className="text-[10px] font-mono text-slate-500">3 probes</span>
          </div>

          <div className="space-y-2">
            {/* OFAC Probe */}
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  <span className="text-[11px] font-medium text-slate-300">OFAC SDN & Watchlists</span>
                </div>
                <ProbeChip status={ofacProbe.status} sourceLabel={ofacProbe.source_label} />
              </div>
              <p className="text-[10px] text-slate-500 mt-1.5 ml-5 leading-snug">
                {ofacProbe.detail}
              </p>
            </div>

            {/* IP Geo Probe */}
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Globe className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  <span className="text-[11px] font-medium text-slate-300">IP Routing & Geolocation</span>
                </div>
                <ProbeChip status={ipGeoProbe.status} sourceLabel={ipGeoProbe.source_label} />
              </div>
              <p className="text-[10px] text-slate-500 mt-1.5 ml-5 leading-snug">
                {ipGeoProbe.detail}
              </p>
            </div>

            {/* Core KYC Probe */}
            <div className="p-2 rounded bg-slate-900/60 border border-slate-800/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  <span className="text-[11px] font-medium text-slate-300">Core KYC & Velocity Baseline</span>
                </div>
                <ProbeChip status={coreKycProbe.status} sourceLabel={coreKycProbe.source_label} />
              </div>
              <p className="text-[10px] text-slate-500 mt-1.5 ml-5 leading-snug">
                {coreKycProbe.detail}
              </p>
            </div>
          </div>
        </div>

        {/* ─── STEP 3: System 2 Synthesis ──────────────────────────── */}
        <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800 step-connector animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <StepBadge n={3} />
              <div>
                <span className="text-xs font-semibold text-slate-200">System 2 Synthesis</span>
                <div className="text-[10px] text-slate-500 mt-0.5">Deep reasoning & claim grounding</div>
              </div>
            </div>
            <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
              {system2Model}
            </span>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider mb-1.5">
                Grounding Integrity
              </div>
              {isInvestigating ? (
                <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                  <Activity className="w-3 h-3 animate-pulse text-cyan-400" />
                  <span>Grounding claims…</span>
                </div>
              ) : !result ? (
                <span className="text-[10px] font-mono text-slate-500">AWAITING TRIAGE</span>
              ) : (
                <GroundingBadge status={result.grounding_status} />
              )}
            </div>
            <div>
              <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider mb-1.5">
                Deterministic Gate
              </div>
              <span className="text-[10px] font-mono text-cyan-300">
                {isInvestigating
                  ? 'EVALUATING CONSTRAINTS...'
                  : quarantinedCount > 0
                  ? `CONTAINMENT ACTIVE (${quarantinedCount} quarantined)`
                  : result
                  ? 'PASSED (0 quarantined)'
                  : 'STANDBY'}
              </span>
            </div>
          </div>
        </div>

        {/* ─── STEP 4: Measured Roundtrip Telemetry ────────────────── */}
        <div className="p-3 bg-slate-950/50 rounded-lg border border-slate-800/60 animate-fade-in">
          <div className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2 text-slate-400">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[11px]">Measured Roundtrip Telemetry</span>
            </div>
            {isInvestigating ? (
              <span className="text-[11px] text-amber-400 flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" />
                In-flight…
              </span>
            ) : latencyMs != null ? (
              <span className="text-cyan-300 font-semibold text-[12px]">
                ⏱ {latencyS}s ({latencyMs.toLocaleString()} ms)
              </span>
            ) : (
              <span className="text-slate-500 text-[11px] font-mono">
                ⏱ Ready
              </span>
            )}
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-600">
            <Cpu className="w-3 h-3" />
            <span>
              {backendStatus === 'connected' ? 'Live backend response — Gemini API & Deterministic Validation' : 'Backend offline — service disconnected'}
            </span>
          </div>
        </div>

      </div>
    </section>
  );
}
