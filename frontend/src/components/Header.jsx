/**
 * Header.jsx — Sticky top navigation bar + Quick Scenario Selector & Tools
 * ─────────────────────────────────────────────────────────────────
 * Includes:
 *   - Brand & live status
 *   - Quick Scenario Selector pills (A: Benign, B: Sanction Hit, C: Injection)
 *   - Case History drawer toggle with badge count
 *   - Settings modal gear icon with custom key status indicator
 *   - Export Audit Package trigger
 */
import React from "react";
import {
  Shield,
  Download,
  Radio,
  Wifi,
  WifiOff,
  Loader2,
  Settings,
  History,
  Key,
  Presentation,
  Zap,
  Plus,
} from "lucide-react";
import { BACKEND_STATUS } from "../types.js";

// ─────────────────────────────────────────────────────────────────────────────
// Backend Status Indicator
// ─────────────────────────────────────────────────────────────────────────────
function BackendStatusBadge({ status }) {
  if (status === BACKEND_STATUS.CONNECTED) {
    return (
      <span className="hidden sm:inline-flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2 py-0.5 rounded tracking-wide">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <Wifi className="w-3 h-3" />
        API Connected
      </span>
    );
  }
  if (status === BACKEND_STATUS.OFFLINE_FALLBACK) {
    return (
      <span
        className="hidden sm:inline-flex items-center gap-1.5 text-[10px] font-semibold text-amber-400 bg-amber-950/40 border border-amber-800/60 px-2 py-0.5 rounded tracking-wide"
        title="Backend unreachable — deterministic benchmark simulation active"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        <WifiOff className="w-3 h-3" />
        Offline Simulation Mode (Deterministic Benchmark)
      </span>
    );
  }
  // testing / initial
  return (
    <span className="hidden sm:inline-flex items-center gap-1.5 text-[10px] font-semibold text-slate-500 bg-slate-900/60 border border-slate-800 px-2 py-0.5 rounded tracking-wide">
      <Loader2 className="w-3 h-3 animate-spin" />
      Connecting…
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario Selector Button
// ─────────────────────────────────────────────────────────────────────────────
function ScenarioButton({ scnKey, scn, isSelected, onClick }) {
  const colorMap = {
    emerald: {
      active:
        "bg-emerald-950/60 text-emerald-300 border-emerald-500/80 shadow-emerald-950/50 shadow-md",
      inactive:
        "bg-slate-900/60 text-slate-400 border-slate-800 hover:border-emerald-800/60 hover:text-emerald-300",
    },
    rose: {
      active:
        "bg-rose-950/60 text-rose-300 border-rose-500/80 shadow-rose-950/50 shadow-md",
      inactive:
        "bg-slate-900/60 text-slate-400 border-slate-800 hover:border-rose-800/60 hover:text-rose-300",
    },
    amber: {
      active:
        "bg-amber-950/60 text-amber-300 border-amber-500/80 shadow-amber-950/50 shadow-md",
      inactive:
        "bg-slate-900/60 text-slate-400 border-slate-800 hover:border-amber-800/60 hover:text-amber-300",
    },
  };
  const colors = colorMap[scn.color] || colorMap.emerald;

  return (
    <button
      key={scnKey}
      onClick={() => onClick(scnKey)}
      className={`text-xs px-3.5 py-1.5 rounded-lg font-medium transition-all duration-200 flex items-center gap-2 border ${
        isSelected ? colors.active : colors.inactive
      }`}
    >
      <span>{scn.name}</span>
      <span className="text-[10px] opacity-70 font-mono px-1.5 py-0.5 rounded bg-slate-950/60 border border-slate-800/50">
        {scn.case_id}
      </span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Header Component
// ─────────────────────────────────────────────────────────────────────────────
export default function Header({
  backendStatus,
  selectedScenarioKey,
  scenarios,
  onSelectScenario,
  onExportAudit,
  onOpenSettings,
  onOpenHistory,
  customApiKey,
  historyCount = 0,
  isDemoMode = false,
  onToggleDemoMode,
  onResetWorkspace,
}) {
  return (
    <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-md sticky top-0 z-40 px-6 py-3.5">
      <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* ── Brand ─────────────────────────────────────────────────── */}
        <div className="flex items-center gap-3.5">
          <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/30 border border-cyan-500/40 flex items-center justify-center shadow-lg shadow-cyan-950/50 flex-shrink-0">
            <Shield className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-white">
                CEYLIX <span className="text-cyan-400">AI</span>
              </h1>
              <span className="text-[10px] font-bold tracking-widest px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-300 uppercase">
                Evidence-Grounded Risk Investigation
              </span>
              <BackendStatusBadge status={backendStatus} />
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5 font-mono">
              BFSI AI Safety · Deterministic AST Claim Validation · Gemini 2.5 Flash / Pro · Google Cloud
            </p>
          </div>
        </div>

        {/* ── Actions ───────────────────────────────────────────────── */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          {/* Demo / Live Mode Toggle */}
          <button
            onClick={onToggleDemoMode}
            title={isDemoMode ? "Click to switch to Live API Mode" : "Click to switch to Demo Mode"}
            className={`relative inline-flex items-center gap-2 text-xs font-bold px-3.5 py-1.5 rounded-lg border transition-all duration-200 shadow-md ${
              isDemoMode
                ? "bg-amber-950/80 border-amber-500/60 text-amber-300 hover:bg-amber-900/80 hover:border-amber-400 shadow-amber-950/60"
                : "bg-emerald-950/80 border-emerald-500/60 text-emerald-300 hover:bg-emerald-900/80 hover:border-emerald-400 shadow-emerald-950/60"
            }`}
          >
            {isDemoMode ? (
              <Zap className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
            ) : (
              <Wifi className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
            )}
            <span className="tracking-wide">
              {isDemoMode ? "⚡ DEMO MODE (MOCK)" : "🟢 LIVE API MODE"}
            </span>
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                isDemoMode
                  ? "bg-amber-400 animate-pulse"
                  : "bg-emerald-400 animate-pulse"
              }`}
            />
          </button>

          {/* History Drawer Trigger */}
          <button
            onClick={onOpenHistory}
            className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700/80 hover:border-slate-600 text-slate-200 transition-all shadow-sm"
            title="Open Case History Log"
          >
            <History className="w-3.5 h-3.5 text-indigo-400" />
            <span>Case History</span>
            {historyCount > 0 && (
              <span className="ml-1 text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">
                {historyCount}
              </span>
            )}
          </button>

          {/* New Investigation Reset */}
          <button
            onClick={onResetWorkspace}
            className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-cyan-500/50 bg-cyan-950/50 hover:bg-cyan-900/70 hover:border-cyan-400 text-cyan-200 transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:ring-offset-2 focus:ring-offset-slate-900"
            title="Start a new investigation"
            aria-label="Start a new investigation"
          >
            <Plus className="w-3.5 h-3.5 text-cyan-300" />
            <span>New Investigation</span>
          </button>

          {/* Settings Modal Trigger */}
          <button
            onClick={onOpenSettings}
            className="relative inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700/80 hover:border-slate-600 text-slate-200 transition-all shadow-sm"
            title="Configure Pipeline & Custom Gemini Key"
          >
            <Settings className="w-3.5 h-3.5 text-slate-300" />
            <span>Settings</span>
            {customApiKey && (
              <span
                className="w-2 h-2 rounded-full bg-emerald-400 border border-slate-900 absolute -top-0.5 -right-0.5"
                title="Custom Gemini API Key is configured"
              />
            )}
          </button>

          {/* Export Audit Package Trigger */}
          <button
            onClick={onExportAudit}
            className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700/80 hover:border-slate-600 text-slate-200 transition-all shadow-sm"
            title="Download verified claim audit JSON package"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span className="hidden sm:inline">Export Audit</span>
          </button>
        </div>
      </div>
    </header>
  );
}
