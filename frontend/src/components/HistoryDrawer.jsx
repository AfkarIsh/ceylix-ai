/**
 * HistoryDrawer.jsx — Forensic Case History & Audit Investigation Log
 * ──────────────────────────────────────────────────────────────────
 * Slide-over drawer providing instant access to past investigated cases
 * from both the backend repository (/api/v1/cases) and current local session.
 * Allows compliance officers and risk auditors to review past runs.
 */

import React, { useState, useEffect } from "react";
import {
  X,
  History,
  Search,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  Flame,
  ArrowRight,
  Database,
  Filter,
  Trash2,
  ExternalLink,
} from "lucide-react";
import { DISPOSITION, classifyScenario } from "../types.js";

const TIME_GROUPS = [
  { key: "recent", label: "Today / Recent" },
  { key: "month", label: "Previous 30 Days" },
  { key: "past", label: "Earlier / Past Year" },
];

function getTimeGroup(timestamp) {
  const parsed = timestamp ? new Date(timestamp).getTime() : Number.NaN;
  if (Number.isNaN(parsed)) return "past";

  const ageMs = Math.max(0, Date.now() - parsed);
  if (ageMs <= 24 * 60 * 60 * 1000) return "recent";
  if (ageMs <= 30 * 24 * 60 * 60 * 1000) return "month";
  return "past";
}

function formatTimestamp(timestamp) {
  if (!timestamp) return "Timestamp unavailable";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return "Timestamp unavailable";
  return parsed.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function HistoryDrawer({
  isOpen,
  onClose,
  backendUrl,
  localHistory = [],
  onSelectCase,
  onClearLocalHistory,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterDisposition, setFilterDisposition] = useState("ALL");

  if (!isOpen) return null;

  // History log strictly contains user's investigated cases and searched scenarios
  const mergedCases = localHistory.map((item) => ({
    ...item,
    isLocalSession: true,
  }));

  // Filter cases based on search and disposition selector
  const filteredCases = mergedCases.filter((item) => {
    const q = searchQuery.toLowerCase().trim();
    if (q) {
      const matchesSearch =
        (item.case_id || "").toLowerCase().includes(q) ||
        (item.scenario_name || "").toLowerCase().includes(q) ||
        (item.search_query || "").toLowerCase().includes(q) ||
        (item.counterparty_name || "").toLowerCase().includes(q) ||
        (item.memo || "").toLowerCase().includes(q) ||
        (item.payload?.memo || "").toLowerCase().includes(q) ||
        (item.payload?.counterparty_name || "").toLowerCase().includes(q) ||
        (item.category || "").toLowerCase().includes(q) ||
        (String(item.amount) || "").includes(q);

      if (!matchesSearch) return false;
    }

    if (filterDisposition === "ALL") return true;
    if (filterDisposition === "DISMISS")
      return item.disposition_title === DISPOSITION.DISMISS;
    if (filterDisposition === "ESCALATE")
      return item.disposition_title === DISPOSITION.ESCALATE;
    if (filterDisposition === "EMERGENCY")
      return item.disposition_title === DISPOSITION.EMERGENCY;

    return true;
  });

  const groupedCases = TIME_GROUPS.map((group) => ({
    ...group,
    cases: filteredCases
      .filter((item) => getTimeGroup(item.timestamp) === group.key)
      .sort((a, b) => {
        const first = new Date(a.timestamp || 0).getTime();
        const second = new Date(b.timestamp || 0).getTime();
        return (Number.isNaN(second) ? 0 : second) - (Number.isNaN(first) ? 0 : first);
      }),
  })).filter((group) => group.cases.length > 0);

  const getDispositionBadge = (disp) => {
    switch (disp) {
      case DISPOSITION.EMERGENCY:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/15 border border-rose-500/40 text-rose-400">
            <Flame className="w-3 h-3 text-rose-400 animate-pulse" />
            ESCALATED
          </span>
        );
      case DISPOSITION.ESCALATE:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/15 border border-amber-500/40 text-amber-400">
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            ESCALATED
          </span>
        );
      case DISPOSITION.DISMISS:
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 border border-emerald-500/40 text-emerald-400">
            <CheckCircle className="w-3 h-3 text-emerald-400" />
            CLEARED
          </span>
        );
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="history-drawer-title"
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md h-full bg-slate-950 border-l border-slate-800 shadow-2xl flex flex-col animate-slide-left"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="p-5 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h2 id="history-drawer-title" className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
                Incident History Log
                <span className="text-[11px] font-mono font-normal px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                  {mergedCases.length} cases
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Audited benchmark cases & active triage sessions
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close Drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter & Search Bar */}
        <div className="p-4 border-b border-slate-800/80 bg-slate-950 space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by Case ID or scenario..."
              className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1">
              {["ALL", "EMERGENCY", "ESCALATE", "DISMISS"].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setFilterDisposition(filter)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-colors ${
                    filterDisposition === filter
                      ? "bg-indigo-600 text-white font-semibold shadow-sm"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/80"
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>

            {localHistory.length > 0 && (
              <button
                onClick={() => {
                  onClearLocalHistory?.();
                }}
                className="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors"
                title="Clear investigation history"
              >
                <Trash2 className="w-3 h-3" />
                Clear History
              </button>
            )}
          </div>
        </div>

        {/* Cases List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 divide-y divide-slate-800/40">
          {mergedCases.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs font-mono">
              <History className="w-6 h-6 mx-auto mb-2 text-indigo-400 opacity-60" />
              <div className="font-semibold text-slate-400">No investigation cases logged yet</div>
              <p className="text-[11px] text-slate-500 mt-1">Run a triage or search a transaction scenario to add to history.</p>
            </div>
          ) : filteredCases.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs">
              No matching investigation cases found.
            </div>
          ) : (
            groupedCases.map((group) => (
              <section key={group.key} className="space-y-2">
                <div className="sticky top-0 z-10 flex items-center gap-2 bg-slate-950/95 py-1.5 backdrop-blur-sm">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-indigo-300">
                    {group.label}
                  </span>
                  <span className="rounded-full border border-slate-800 bg-slate-900 px-1.5 py-0.5 text-[10px] font-mono text-slate-500">
                    {group.cases.length}
                  </span>
                  <div className="h-px flex-1 bg-slate-800/70" />
                </div>
                {group.cases.map((item, idx) => (
                  <div
                    key={`${group.key}-${item.case_id}-${idx}`}
                    onClick={() => {
                      onSelectCase(item);
                      onClose();
                    }}
                    className="group p-3 rounded-xl border border-transparent hover:border-slate-800 hover:bg-slate-900/60 transition-all cursor-pointer"
                  >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-white group-hover:text-indigo-400 transition-colors">
                        {item.case_id}
                      </span>
                      {item.isLocalSession && (
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          Active Run
                        </span>
                      )}
                      {item.search_query && (
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                          🔍 Searched
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-300 font-medium line-clamp-1">
                      {item.scenario_name}
                    </div>
                    {item.search_query && (
                      <div className="text-[10px] text-cyan-400/80 font-mono italic truncate max-w-[280px]">
                        "{item.search_query}"
                      </div>
                    )}
                  </div>
                  <div>{getDispositionBadge(item.disposition_title)}</div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mt-2 pt-2 border-t border-slate-900">
                  <span className="text-slate-300 font-semibold">
                    ${Number(item.amount || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}{" "}
                    {item.currency || "USD"}
                  </span>
                  <span className="text-slate-500 flex items-center gap-1 group-hover:text-indigo-400 transition-colors">
                    Load Dossier <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
                <div className="mt-1 text-right text-[10px] text-slate-600 font-mono">
                  {formatTimestamp(item.timestamp)}
                </div>
                {item.error_message && (
                  <div className="mt-2 rounded border border-rose-900/60 bg-rose-950/30 px-2 py-1.5 text-[10px] leading-snug text-rose-300">
                    Investigation failed: {item.error_message}
                  </div>
                )}
                  </div>
                ))}
              </section>
            ))
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/40 text-xs text-slate-500 flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-mono text-[11px]">
            <Database className="w-3.5 h-3.5 text-indigo-400" />
            Backend Sync Active
          </span>
          <span className="text-[11px] font-mono">
            Firestore v1
          </span>
        </div>
      </div>
    </div>
  );
}
