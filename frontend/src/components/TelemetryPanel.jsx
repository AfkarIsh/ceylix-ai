/**
 * TelemetryPanel.jsx — Panel 1: Transaction Telemetry Payload & Sensitivity Controls
 * ─────────────────────────────────────────────────────────────────────────────────
 * Displays raw transaction fields with masked account ID, edit mode,
 * adversarial content warning for Scenario C, Risk Sensitivity selector, and the Execute button.
 *
 * Props:
 *   payload                 object  — active transaction payload
 *   isEditing               boolean — whether edit mode is active
 *   isInvestigating         boolean — loading state
 *   backendStatus           string  — 'connected' | 'offline_fallback' | 'testing'
 *   sensitivityMode         string  — 'standard' | 'strict'
 *   onChangeSensitivityMode (mode: string) => void
 *   onEditToggle            () => void
 *   onPayloadChange         (field: string, value: string) => void
 *   onRunTriage             () => void
 */
import React, { useMemo } from 'react';
import {
  Database,
  Edit3,
  Lock,
  Globe,
  ChevronRight,
  Zap,
  Loader2,
  AlertTriangle,
  Server,
  Sliders,
  ShieldAlert,
} from 'lucide-react';
import { SENSITIVITY_MODE, SENSITIVITY_CONFIG } from '../types.js';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function maskAccount(id) {
  if (!id) return 'acc_••••••••';
  const clean = id.replace(/^acc_/, '');
  if (clean.length <= 4) return `acc_••••${clean}`;
  return `acc_••••${clean.slice(-4)}`;
}

function formatCurrency(amount, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style:                 'currency',
    currency:              currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(amount) || 0);
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  const parts = ts.split('T');
  if (parts.length < 2) return ts;
  return parts[1].replace('Z', '') + ' UTC';
}

// Detect adversarial injection tokens in any payload field
const INJECTION_PATTERNS = [
  /\bsystem override\b/i,
  /\bignore all\b/i,
  /\bprevious instructions\b/i,
  /\bdo not check\b/i,
  /\bprotocol zero\b/i,
  /\boverride code\b/i,
  /\bboard member\b/i,
  /\bpre-cleared by\b/i,
];

function hasAdversarialContent(payload) {
  const fields = [payload.counterparty_name, payload.memo];
  return fields.some(
    (f) => f && INJECTION_PATTERNS.some((rx) => rx.test(f))
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────
function FieldLabel({ children }) {
  return (
    <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider mb-0.5">
      {children}
    </div>
  );
}

function DataCell({ children, className = '' }) {
  return (
    <div className={`p-2.5 bg-slate-950/80 rounded-lg border border-slate-800/80 ${className}`}>
      {children}
    </div>
  );
}

function EditableField({ value, onChange, multiline = false }) {
  const cls =
    'w-full mt-0.5 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded text-[11px] text-slate-100 focus:outline-none focus:border-cyan-500 transition-colors resize-none';
  if (multiline) {
    return (
      <textarea
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cls}
      />
    );
  }
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cls}
    />
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TelemetryPanel Component
// ─────────────────────────────────────────────────────────────────────────────
export default function TelemetryPanel({
  payload,
  isEditing,
  isInvestigating,
  backendStatus,
  sensitivityMode = SENSITIVITY_MODE.STANDARD,
  onChangeSensitivityMode,
  onEditToggle,
  onPayloadChange,
  onRunTriage,
}) {
  const hasInjection = useMemo(() => hasAdversarialContent(payload), [payload]);
  const isIranCorridor = payload.counterparty_country === 'IR';

  const currentSensitivity = SENSITIVITY_CONFIG[sensitivityMode] || SENSITIVITY_CONFIG[SENSITIVITY_MODE.STANDARD];

  return (
    <section className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-xl relative overflow-hidden backdrop-blur-sm">
      {/* ── Panel Header ────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-bold tracking-wider uppercase text-slate-200">
            Panel 1: Transaction Telemetry
          </h2>
        </div>
        <button
          onClick={onEditToggle}
          disabled={isInvestigating}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded transition-colors ${
            isEditing
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
          title={isEditing ? 'Save edits' : 'Edit raw payload'}
        >
          <Edit3 className="w-3.5 h-3.5" />
          <span>{isEditing ? 'Done Editing' : 'Edit Payload'}</span>
        </button>
      </div>

      {/* ── Adversarial Content Warning Banner ──────────────────────── */}
      {hasInjection && (
        <div className="mt-3 p-3 bg-amber-950/40 border border-amber-600/60 rounded-lg flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-[11px] text-amber-200">
            <span className="font-semibold block text-amber-300">
              Adversarial System Override Detected
            </span>
            Payload contains control instructions intended to manipulate model risk scores.
            Ceylix AI's AST evidence validator will quarantine these tokens automatically.
          </div>
        </div>
      )}

      {/* ── Risk Sensitivity Controls ───────────────────────────────── */}
      <div className="mt-3.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            Risk Sensitivity Mode
          </label>
          {sensitivityMode === SENSITIVITY_MODE.STRICT ? (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/40 text-rose-300 font-semibold flex items-center gap-1">
              <ShieldAlert className="w-3 h-3 text-rose-400" />
              Strict / Zero-Tolerance
            </span>
          ) : (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
              Standard Enterprise
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            type="button"
            onClick={() => onChangeSensitivityMode && onChangeSensitivityMode(SENSITIVITY_MODE.STANDARD)}
            className={`px-2.5 py-1.5 rounded-lg text-left text-xs transition-all border ${
              sensitivityMode === SENSITIVITY_MODE.STANDARD
                ? 'bg-cyan-950/40 border-cyan-500/60 text-cyan-200 font-medium shadow-sm'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="font-semibold text-[11px]">Standard Mode</div>
            <div className="text-[10px] text-slate-400 opacity-80 mt-0.5">OFAC 0.85 · $10k CTR</div>
          </button>

          <button
            type="button"
            onClick={() => onChangeSensitivityMode && onChangeSensitivityMode(SENSITIVITY_MODE.STRICT)}
            className={`px-2.5 py-1.5 rounded-lg text-left text-xs transition-all border ${
              sensitivityMode === SENSITIVITY_MODE.STRICT
                ? 'bg-rose-950/40 border-rose-500/60 text-rose-200 font-medium shadow-sm'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="font-semibold text-[11px] text-rose-300">Strict Compliance</div>
            <div className="text-[10px] text-slate-400 opacity-80 mt-0.5">OFAC 0.70 · $2.5k CTR</div>
          </button>
        </div>
      </div>

      {/* ── Transaction Data Fields Grid ─────────────────────────────── */}
      <div className="mt-3.5 space-y-2.5 flex-1">

        {/* Row 1: Amount & Timestamp */}
        <div className="grid grid-cols-2 gap-2.5">
          <DataCell>
            <FieldLabel>Amount & Currency</FieldLabel>
            {isEditing ? (
              <EditableField
                value={String(payload.amount)}
                onChange={(val) => onPayloadChange('amount', val)}
              />
            ) : (
              <div className="font-mono font-bold text-slate-100 text-sm mt-0.5">
                {formatCurrency(payload.amount, payload.currency)}
              </div>
            )}
          </DataCell>

          <DataCell>
            <FieldLabel>Timestamp</FieldLabel>
            <div className="font-mono text-slate-300 text-xs mt-0.5">
              {formatTimestamp(payload.timestamp)}
            </div>
          </DataCell>
        </div>

        {/* Row 2: Account ID & Channel */}
        <div className="grid grid-cols-2 gap-2.5">
          <DataCell>
            <FieldLabel>Source Account (Masked)</FieldLabel>
            <div className="flex items-center gap-1.5 font-mono text-slate-400 text-xs mt-0.5">
              <Lock className="w-3 h-3 text-slate-500 flex-shrink-0" />
              <span>{maskAccount(payload.account_id)}</span>
            </div>
          </DataCell>

          <DataCell>
            <FieldLabel>Channel / Rail</FieldLabel>
            <div className="font-mono text-slate-300 text-xs mt-0.5">
              {payload.channel || 'WIRE'}
            </div>
          </DataCell>
        </div>

        {/* Row 3: Routing corridor */}
        <DataCell className={isIranCorridor ? 'border-rose-800/80 bg-rose-950/20' : ''}>
          <FieldLabel>Routing Corridor</FieldLabel>
          <div className="flex items-center gap-2 mt-0.5">
            <Globe className="w-3.5 h-3.5 text-slate-400" />
            <span className="font-mono text-xs text-slate-300">
              {payload.origin_country || 'US'}
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
            <span
              className={`font-mono text-xs font-bold ${
                isIranCorridor ? 'text-rose-400 underline decoration-rose-500/60' : 'text-slate-300'
              }`}
            >
              {payload.counterparty_country || 'US'}
            </span>
            {isIranCorridor && (
              <span className="ml-auto text-[9px] font-bold font-mono px-1.5 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-700/60">
                HIGH RISK CORRIDOR
              </span>
            )}
          </div>
        </DataCell>

        {/* Row 4: Device IP */}
        <DataCell>
          <FieldLabel>Origin Device IP</FieldLabel>
          {isEditing ? (
            <EditableField
              value={payload.device_ip || ''}
              onChange={(val) => onPayloadChange('device_ip', val)}
            />
          ) : (
            <div className="font-mono text-slate-400 text-xs mt-0.5 flex items-center gap-1.5">
              <Server className="w-3 h-3 text-slate-500" />
              <span>{payload.device_ip || '198.51.100.24'}</span>
            </div>
          )}
        </DataCell>

        {/* Row 5: Beneficiary Name */}
        <DataCell>
          <FieldLabel>Beneficiary Entity Name</FieldLabel>
          {isEditing ? (
            <EditableField
              value={payload.counterparty_name || ''}
              onChange={(val) => onPayloadChange('counterparty_name', val)}
            />
          ) : (
            <div
              className={`text-xs mt-0.5 font-medium ${
                hasInjection && INJECTION_PATTERNS.some((rx) => rx.test(payload.counterparty_name))
                  ? 'text-amber-300 font-mono text-[11px] bg-amber-950/30 p-1 rounded border border-amber-800/40'
                  : 'text-slate-200'
              }`}
            >
              {payload.counterparty_name}
            </div>
          )}
        </DataCell>

        {/* Row 6: Beneficiary Bank */}
        <DataCell>
          <FieldLabel>Beneficiary Financial Institution</FieldLabel>
          <div className="text-xs text-slate-300 mt-0.5 truncate">
            {payload.counterparty_bank || '—'}
          </div>
        </DataCell>

        {/* Row 7: Payment Memo */}
        <DataCell>
          <FieldLabel>Payment Memo / Remittance Info</FieldLabel>
          {isEditing ? (
            <EditableField
              multiline
              value={payload.memo || ''}
              onChange={(val) => onPayloadChange('memo', val)}
            />
          ) : (
            <div
              className={`text-xs mt-0.5 italic leading-relaxed line-clamp-3 ${
                hasInjection && INJECTION_PATTERNS.some((rx) => rx.test(payload.memo))
                  ? 'text-amber-300 not-italic font-mono text-[11px] bg-amber-950/30 p-1.5 rounded border border-amber-800/40'
                  : 'text-slate-400'
              }`}
            >
              "{payload.memo}"
            </div>
          )}
        </DataCell>

        {/* Counterparty account (read-only) */}
        <DataCell>
          <FieldLabel>Beneficiary Account Ref</FieldLabel>
          <div className="font-mono text-slate-500 text-[10px] mt-0.5 truncate">
            {payload.counterparty_account}
          </div>
        </DataCell>

      </div>

      {/* ── Execute Button ─────────────────────────────────────────── */}
      <div className="mt-5 pt-4 border-t border-slate-800">
        {backendStatus === 'connected' && (
          <div className="flex items-center gap-1.5 mb-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] text-emerald-400 font-mono">
              Live Gemini endpoint active — simulation fallback on error
            </span>
          </div>
        )}
        {backendStatus === 'offline_fallback' && (
          <div className="flex items-center gap-1.5 mb-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span className="text-[10px] text-amber-400 font-mono">
              Offline — deterministic benchmark simulation
            </span>
          </div>
        )}
        <button
          id="btn-run-triage"
          onClick={onRunTriage}
          disabled={isInvestigating}
          className="w-full py-2.5 px-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 active:from-cyan-700 active:to-blue-700 text-white rounded-lg font-bold text-xs tracking-widest uppercase transition-all duration-200 shadow-lg shadow-cyan-950/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isInvestigating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Executing Forensic Probes…</span>
            </>
          ) : (
            <>
              <Zap className="w-4 h-4 text-cyan-200 fill-cyan-200" />
              <span>Execute Forensic Triage</span>
            </>
          )}
        </button>
      </div>
    </section>
  );
}
