/**
 * TelemetryPanel.jsx — Gemini-Style Centered Pill Bar & Active Telemetry Ingestion
 * ─────────────────────────────────────────────────────────────────────────────────
 * Replicates the Google Gemini chat interface:
 *   - Hero Landing State: Centered greeting + long pill chat bar + quick chips.
 *   - Docked Workbench State: Docked pill bar in Panel 1 + telemetry baseline + sensitivity mode.
 */
import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Database,
  Edit3,
  Lock,
  Globe,
  Zap,
  Loader2,
  AlertTriangle,
  Sliders,
  ShieldAlert,
  Sparkles,
  ArrowUp,
  Plus,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  RotateCcw,
} from 'lucide-react';
import {
  SENSITIVITY_MODE,
  SENSITIVITY_CONFIG,
  AVAILABLE_MODELS,
  PRESET_SCENARIOS,
  parseNaturalLanguageWire,
} from '../types.js';

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
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(amount) || 0);
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
  const fields = [payload?.counterparty_name, payload?.memo];
  return fields.some((f) => f && INJECTION_PATTERNS.some((rx) => rx.test(f)));
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
// GeminiPillBar Component (True Gemini-Style Long Pill)
// ─────────────────────────────────────────────────────────────────────────────
export function GeminiPillBar({
  inputText,
  setInputText,
  onSend,
  isInvestigating,
  selectedModel = 'gemini-2.5-flash',
  onChangeModel,
  onSelectScenario,
  scenarios = PRESET_SCENARIOS,
  onResetWorkspace,
  resetKey = 0,
  variant = 'docked', // 'hero' | 'docked'
}) {
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [isPresetDropdownOpen, setIsPresetDropdownOpen] = useState(false);

  useEffect(() => {
    setInputText('');
  }, [resetKey, setInputText]);

  const activeModelObj = useMemo(
    () => AVAILABLE_MODELS.find((m) => m.id === selectedModel) || AVAILABLE_MODELS[0],
    [selectedModel]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handlePresetSelect = (key) => {
    setIsPresetDropdownOpen(false);
    onSelectScenario?.(key);
  };

  const isHero = variant === 'hero';

  return (
    <div className={`relative w-full ${isHero ? 'max-w-2xl mx-auto' : ''}`}>
      {/* ── The Gemini Pill Container ─────────────────────────────── */}
      <div
        className={`w-full rounded-full bg-slate-900/95 border border-slate-700/80 shadow-2xl flex items-center transition-all duration-200 backdrop-blur-md focus-within:border-cyan-500/80 focus-within:ring-2 focus-within:ring-cyan-500/25 ${isHero ? 'px-4 py-2.5 sm:px-5 sm:py-3.5 gap-2.5 sm:gap-3.5' : 'px-3.5 py-2 gap-2'
          }`}
      >
        {!isHero && onResetWorkspace && (
          <button
            type="button"
            onClick={() => {
              setInputText('');
              onResetWorkspace();
            }}
            className="w-7 h-7 rounded-full flex items-center justify-center bg-cyan-950/60 hover:bg-cyan-900/80 text-cyan-300 hover:text-cyan-100 border border-cyan-500/40 hover:border-cyan-400 transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-400/60 flex-shrink-0"
            title="Start a new investigation"
            aria-label="Start a new investigation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}

        {/* Left: Quick Attach / Preset (+) Button */}
        <div className="relative flex-shrink-0">
          <button
            type="button"
            onClick={() => {
              setIsPresetDropdownOpen(!isPresetDropdownOpen);
              setIsModelDropdownOpen(false);
            }}
            className={`rounded-full flex items-center justify-center transition-all ${isHero
                ? 'w-8 h-8 sm:w-9 sm:h-9 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white'
                : 'w-7 h-7 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white'
              }`}
            title="1-Click benchmark scenarios (Case A, B, C)"
          >
            <Plus className={isHero ? 'w-4 h-4 sm:w-4.5 sm:h-4.5' : 'w-3.5 h-3.5'} />
          </button>

          {/* Preset Popover Menu */}
          {isPresetDropdownOpen && (
            <div className="absolute left-0 bottom-full mb-2 w-72 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl p-2 z-50 text-left backdrop-blur-xl">
              <div className="text-[10px] uppercase font-bold text-slate-400 px-3 py-1.5 tracking-wider">
                Benchmark Scenario Presets
              </div>
              {Object.entries(scenarios).map(([key, scn]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => handlePresetSelect(key)}
                  className="w-full text-left px-3 py-2 rounded-xl text-xs hover:bg-slate-800/90 transition-colors flex items-center justify-between group"
                >
                  <div className="min-w-0 pr-2">
                    <div className="font-semibold text-slate-200 group-hover:text-cyan-300 transition-colors truncate">
                      {scn.name}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono truncate">
                      {scn.case_id} · {scn.tag}
                    </div>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 transition-colors flex-shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Center: Seamless Transparent Input */}
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Ceylix AI to triage a transaction, paste SWIFT message..."
          className={`flex-1 bg-transparent text-slate-100 placeholder-slate-400/80 focus:outline-none font-sans min-w-0 ${isHero ? 'text-xs sm:text-sm' : 'text-xs'
            }`}
        />

        {/* Right: Model Selector Pill */}
        <div className="relative flex-shrink-0">
          <button
            type="button"
            onClick={() => {
              setIsModelDropdownOpen(!isModelDropdownOpen);
              setIsPresetDropdownOpen(false);
            }}
            className={`flex items-center gap-1.5 rounded-full font-medium transition-colors border ${isHero
                ? 'px-3 py-1.5 text-xs bg-slate-800/90 hover:bg-slate-700/90 border-slate-700 text-slate-200'
                : 'px-2.5 py-1 text-[11px] bg-slate-800/70 hover:bg-slate-700/80 border-slate-700/80 text-slate-300'
              }`}
            title="Select Gemini cognitive tier"
          >
            <span className="text-cyan-400 font-semibold truncate">
              {activeModelObj.name.replace('Gemini ', '')}
            </span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {/* Model Dropdown Menu */}
          {isModelDropdownOpen && (
            <div className="absolute right-0 bottom-full mb-2 w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl p-1.5 z-50 text-left backdrop-blur-xl">
              <div className="text-[10px] uppercase font-bold text-slate-400 px-2.5 py-1 tracking-wider">
                Gemini Cognitive Tiers
              </div>
              {AVAILABLE_MODELS.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    onChangeModel?.(m.id);
                    setIsModelDropdownOpen(false);
                  }}
                  className={`w-full text-left p-2 rounded-xl text-xs flex items-start gap-2.5 transition-colors ${selectedModel === m.id
                      ? 'bg-cyan-950/70 border border-cyan-500/50 text-cyan-200'
                      : 'hover:bg-slate-800 text-slate-300'
                    }`}
                >
                  <span className="text-base mt-0.5">{m.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-100 flex items-center justify-between">
                      {m.name}
                      {selectedModel === m.id && (
                        <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                      )}
                    </div>
                    <div className="text-[10px] text-slate-400 leading-tight mt-0.5">
                      {m.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Circular Send Button */}
        <button
          type="button"
          onClick={onSend}
          disabled={isInvestigating}
          className={`rounded-full flex items-center justify-center transition-all flex-shrink-0 shadow-lg shadow-cyan-950/60 disabled:opacity-50 disabled:cursor-not-allowed ${isHero
              ? 'w-8 h-8 sm:w-9 sm:h-9 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white'
              : 'w-7 h-7 sm:w-8 sm:h-8 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white'
            }`}
          title="Send query / Execute triage"
        >
          {isInvestigating ? (
            <Loader2 className={isHero ? 'w-4 h-4 animate-spin' : 'w-3.5 h-3.5 animate-spin'} />
          ) : (
            <ArrowUp className={isHero ? 'w-4 h-4 sm:w-4.5 sm:h-4.5' : 'w-3.5 h-3.5'} />
          )}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GeminiHeroView Component (Centered Landing View like Gemini Web)
// ─────────────────────────────────────────────────────────────────────────────
export function GeminiHeroView({
  onRunTriage,
  isInvestigating,
  selectedModel,
  onChangeModel,
  onSelectScenario,
  scenarios = PRESET_SCENARIOS,
  payload,
  resetKey = 0,
}) {
  const [inputText, setInputText] = useState('');

  useEffect(() => {
    setInputText('');
  }, [resetKey]);

  const handleSend = () => {
    if (isInvestigating) return;
    const submittedText = inputText.trim();
    setInputText('');
    if (!submittedText) {
      onRunTriage?.(payload);
      return;
    }
    const parsed = parseNaturalLanguageWire(submittedText, payload);
    if (parsed._matchedPresetKey && onSelectScenario) {
      onSelectScenario(parsed._matchedPresetKey);
      return;
    }
    const searchCaseId = parsed.case_id || `CASE-SRCH-${Math.floor(100000 + Math.random() * 900000)}`;
    onRunTriage?.(parsed, searchCaseId);
  };

  const handleQuickChipClick = (scenarioKey) => {
    const scn = scenarios[scenarioKey];
    if (scn) {
      if (onSelectScenario) {
        onSelectScenario(scenarioKey);
      } else {
        onRunTriage?.(scn.payload);
      }
    }
  };

  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center text-center px-4 py-8 relative">
      {/* Background Soft Radial Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[350px] bg-gradient-to-b from-cyan-600/10 via-blue-600/10 to-transparent blur-3xl pointer-events-none rounded-full" />

      {/* Main Centered Heading */}
      <div className="max-w-2xl mx-auto mb-8 space-y-3 z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-700/80 text-cyan-300 text-xs font-mono mb-2 shadow-sm">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>Gemini 2.5 Cognitive Compliance Engine</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-100 leading-tight">
          What risk investigation can Ceylix AI help you run today?
        </h1>
        <p className="text-sm text-slate-400 max-w-lg mx-auto">
          Type or paste any raw transaction text, SWIFT MT103 wire, or select a core benchmark scenario below.
        </p>
      </div>

      {/* The Centered Pill Bar */}
      <div className="w-full max-w-2xl z-10">
        <GeminiPillBar
          inputText={inputText}
          setInputText={setInputText}
          onSend={handleSend}
          isInvestigating={isInvestigating}
          selectedModel={selectedModel}
          onChangeModel={onChangeModel}
          onSelectScenario={onSelectScenario}
          scenarios={scenarios}
          resetKey={resetKey}
          variant="hero"
        />

        {/* Quick Suggestion Chips below pill bar */}
        <div className="flex flex-wrap items-center justify-center gap-2.5 mt-5">
          <button
            type="button"
            onClick={() => handleQuickChipClick('scenarioA')}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-slate-700/70 hover:border-emerald-500/50 text-slate-300 hover:text-emerald-300 text-xs transition-all shadow-sm group"
          >
            <span className="text-emerald-400">⚡</span>
            <span>Benign Retail Wire</span>
            <span className="text-[10px] text-slate-500 font-mono group-hover:text-emerald-400/80">
              (CASE-051)
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleQuickChipClick('scenarioB')}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-slate-700/70 hover:border-rose-500/50 text-slate-300 hover:text-rose-300 text-xs transition-all shadow-sm group"
          >
            <span className="text-rose-400">🚨</span>
            <span>Sanction Hit & Geo Mismatch</span>
            <span className="text-[10px] text-slate-500 font-mono group-hover:text-rose-400/80">
              (CASE-021)
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleQuickChipClick('scenarioC')}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-slate-700/70 hover:border-amber-500/50 text-slate-300 hover:text-amber-300 text-xs transition-all shadow-sm group"
          >
            <span className="text-amber-400">🛡️</span>
            <span>Prompt Injection Attack</span>
            <span className="text-[10px] text-slate-500 font-mono group-hover:text-amber-400/80">
              (CASE-041)
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TelemetryPanel Component (Docked Panel 1 Mode)
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
  selectedModel = 'gemini-2.5-flash',
  onChangeModel,
  onSelectScenario,
  scenarios = PRESET_SCENARIOS,
  onResetWorkspace,
  resetKey = 0,
}) {
  const [inputText, setInputText] = useState('');
  const hasInjection = useMemo(() => hasAdversarialContent(payload), [payload]);

  useEffect(() => {
    setInputText('');
  }, [resetKey]);

  const handleSend = () => {
    if (isInvestigating) return;
    const submittedText = inputText.trim();
    setInputText('');
    if (!submittedText) {
      onRunTriage?.(payload);
      return;
    }
    const parsed = parseNaturalLanguageWire(submittedText, payload);
    if (parsed._matchedPresetKey && onSelectScenario) {
      onSelectScenario(parsed._matchedPresetKey);
      return;
    }
    const searchCaseId = parsed.case_id || `CASE-SRCH-${Math.floor(100000 + Math.random() * 900000)}`;
    onRunTriage?.(parsed, searchCaseId);
  };

  return (
    <section className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-4 sm:p-5 flex flex-col justify-between shadow-xl relative overflow-hidden backdrop-blur-sm space-y-4">
      {/* ── Top Header with New Case reset button ──────────────────── */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-bold tracking-wider uppercase text-slate-200">
            Panel 1: Telemetry & Ingestion
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {backendStatus === 'connected' ? (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live Backend
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono text-rose-400 bg-rose-950/40 border border-rose-500/30 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              Backend Offline
            </span>
          )}
        </div>
      </div>

      {/* ── Docked Gemini Pill Bar at Top of Panel 1 ──────────────── */}
      <GeminiPillBar
        inputText={inputText}
        setInputText={setInputText}
        onSend={handleSend}
        isInvestigating={isInvestigating}
        selectedModel={selectedModel}
        onChangeModel={onChangeModel}
        onSelectScenario={onSelectScenario}
        scenarios={scenarios}
        variant="docked"
        onResetWorkspace={onResetWorkspace}
        resetKey={resetKey}
      />

      {/* ── Adversarial Content Warning Banner ──────────────────────── */}
      {hasInjection && (
        <div className="p-3 bg-amber-950/40 border border-amber-600/60 rounded-lg flex items-start gap-2.5">
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

      {/* ── ACTIVE TELEMETRY INSPECTION CARD ────────────────────────── */}
      <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Database className="w-3 h-3 text-cyan-400" />
              Locked Telemetry Baseline
            </span>
            <span className="font-mono text-[10px] px-1.5 py-0.2 bg-slate-900 border border-slate-800 rounded text-cyan-400">
              {payload.transaction_id}
            </span>
          </div>

          <button
            onClick={onEditToggle}
            disabled={isInvestigating}
            className={`flex items-center gap-1 text-[11px] px-2.5 py-1 rounded transition-colors ${isEditing
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'text-slate-400 hover:text-slate-200 bg-slate-900/60 hover:bg-slate-800 border border-slate-800'
              }`}
            title={isEditing ? 'Close manual editor' : 'Manually edit fields'}
          >
            <Edit3 className="w-3 h-3" />
            <span>{isEditing ? 'Done' : 'Manual Edit'}</span>
          </button>
        </div>

        {/* Telemetry Summary Badges */}
        <div className="grid grid-cols-3 gap-2">
          {/* Amount Badge */}
          <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800/80">
            <FieldLabel>Amount (USD)</FieldLabel>
            {isEditing ? (
              <EditableField
                value={payload.amount}
                onChange={(v) => onPayloadChange('amount', v)}
              />
            ) : (
              <div className="font-mono text-sm font-bold text-slate-100">
                {formatCurrency(payload.amount, payload.currency)}
              </div>
            )}
          </div>

          {/* Corridor Badge */}
          <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800/80">
            <FieldLabel>Corridor Route</FieldLabel>
            {isEditing ? (
              <div className="flex items-center gap-1 mt-0.5">
                <input
                  type="text"
                  maxLength={2}
                  value={payload.origin_country || 'US'}
                  onChange={(e) => onPayloadChange('origin_country', e.target.value.toUpperCase())}
                  className="w-10 px-1 py-1 bg-slate-900 border border-slate-700 rounded text-[11px] text-center font-mono"
                />
                <span className="text-slate-500">➔</span>
                <input
                  type="text"
                  maxLength={2}
                  value={payload.counterparty_country || 'US'}
                  onChange={(e) => onPayloadChange('counterparty_country', e.target.value.toUpperCase())}
                  className="w-10 px-1 py-1 bg-slate-900 border border-slate-700 rounded text-[11px] text-center font-mono"
                />
              </div>
            ) : (
              <div className="font-mono text-xs font-semibold text-slate-200 flex items-center gap-1.5 mt-0.5">
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                  {payload.origin_country || 'US'}
                </span>
                <span className="text-slate-500">➔</span>
                <span
                  className={`px-1.5 py-0.5 rounded ${payload.counterparty_country === 'IR' || payload.counterparty_country === 'KP'
                      ? 'bg-rose-950 text-rose-300 border border-rose-800/60 font-bold'
                      : 'bg-slate-800 text-slate-300'
                    }`}
                >
                  {payload.counterparty_country || 'US'}
                </span>
              </div>
            )}
          </div>

          {/* Channel Badge */}
          <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800/80">
            <FieldLabel>Channel Protocol</FieldLabel>
            {isEditing ? (
              <EditableField
                value={payload.channel}
                onChange={(v) => onPayloadChange('channel', v)}
              />
            ) : (
              <div className="font-mono text-xs text-slate-300 mt-0.5 truncate">
                {payload.channel}
              </div>
            )}
          </div>
        </div>

        {/* Detailed Metadata Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {/* Beneficiary */}
          <DataCell>
            <FieldLabel>Counterparty Beneficiary</FieldLabel>
            {isEditing ? (
              <EditableField
                value={payload.counterparty_name}
                onChange={(v) => onPayloadChange('counterparty_name', v)}
              />
            ) : (
              <div className="font-semibold text-slate-200 text-xs truncate" title={payload.counterparty_name}>
                {payload.counterparty_name}
              </div>
            )}
          </DataCell>

          {/* Institution */}
          <DataCell>
            <FieldLabel>Settlement Institution</FieldLabel>
            {isEditing ? (
              <EditableField
                value={payload.counterparty_bank}
                onChange={(v) => onPayloadChange('counterparty_bank', v)}
              />
            ) : (
              <div className="text-slate-300 text-xs truncate" title={payload.counterparty_bank}>
                {payload.counterparty_bank}
              </div>
            )}
          </DataCell>

          {/* Device IP */}
          <DataCell>
            <FieldLabel>Client Device IP</FieldLabel>
            {isEditing ? (
              <EditableField
                value={payload.device_ip || ''}
                onChange={(v) => onPayloadChange('device_ip', v)}
              />
            ) : (
              <div className="font-mono text-[11px] text-cyan-400 mt-0.5 flex items-center gap-1.5">
                <Globe className="w-3 h-3 text-slate-500" />
                <span>{payload.device_ip || '198.51.100.24'}</span>
              </div>
            )}
          </DataCell>

          {/* Account */}
          <DataCell>
            <FieldLabel>Originating Account</FieldLabel>
            <div className="font-mono text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
              <Lock className="w-3 h-3 text-slate-500" />
              <span>{maskAccount(payload.account_id)}</span>
            </div>
          </DataCell>
        </div>

        {/* Memo / Purpose */}
        <DataCell>
          <FieldLabel>Payment Memo / Instruction Remittance</FieldLabel>
          {isEditing ? (
            <EditableField
              value={payload.memo || ''}
              onChange={(v) => onPayloadChange('memo', v)}
              multiline
            />
          ) : (
            <div
              className={`text-[11px] mt-0.5 leading-relaxed line-clamp-2 ${hasInjection && INJECTION_PATTERNS.some((rx) => rx.test(payload.memo))
                  ? 'text-amber-300 font-mono bg-amber-950/30 p-1.5 rounded border border-amber-800/40'
                  : 'text-slate-400 italic'
                }`}
            >
              "{payload.memo || 'No memo provided'}"
            </div>
          )}
        </DataCell>
      </div>

      {/* ── Risk Sensitivity Controls ───────────────────────────────── */}
      <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            Risk Sensitivity Mode
          </label>
          {sensitivityMode === SENSITIVITY_MODE.STRICT ? (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/40 text-rose-300 font-semibold flex items-center gap-1">
              <ShieldAlert className="w-3 h-3 text-rose-400" />
              Strict Zero-Tolerance
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
            onClick={() => onChangeSensitivityMode?.(SENSITIVITY_MODE.STANDARD)}
            className={`p-2 rounded-lg text-left transition-all border ${sensitivityMode === SENSITIVITY_MODE.STANDARD
                ? 'bg-cyan-950/60 border-cyan-500/70 text-cyan-200 shadow-md shadow-cyan-950/50'
                : 'bg-slate-900/50 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700'
              }`}
          >
            <div className="text-xs font-semibold flex items-center justify-between">
              Standard Mode
              {sensitivityMode === SENSITIVITY_MODE.STANDARD && (
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              )}
            </div>
            <div className="text-[10px] text-slate-500 leading-tight mt-0.5">
              $10,000 CTR rule · Standard OFAC
            </div>
          </button>

          <button
            type="button"
            onClick={() => onChangeSensitivityMode?.(SENSITIVITY_MODE.STRICT)}
            className={`p-2 rounded-lg text-left transition-all border ${sensitivityMode === SENSITIVITY_MODE.STRICT
                ? 'bg-rose-950/60 border-rose-500/70 text-rose-200 shadow-md shadow-rose-950/50'
                : 'bg-slate-900/50 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:border-slate-700'
              }`}
          >
            <div className="text-xs font-semibold flex items-center justify-between">
              Strict Mode
              {sensitivityMode === SENSITIVITY_MODE.STRICT && (
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              )}
            </div>
            <div className="text-[10px] text-slate-500 leading-tight mt-0.5">
              $2,500 CTR trigger · Zero tolerance
            </div>
          </button>
        </div>
      </div>
    </section>
  );
}
