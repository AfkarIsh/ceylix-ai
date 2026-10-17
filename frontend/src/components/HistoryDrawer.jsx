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

export default function HistoryDrawer({
  isOpen,
  onClose,
  backendUrl,
  localHistory = [],
  onSelectCase,
  onClearLocalHistory,
}) {
  const [backendCases, setBackendCases] = useState([]);
  const [loadingBackend, setLoadingBackend] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterDisposition, setFilterDisposition] = useState("ALL");

  // Fetch benchmark repository cases on open
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setLoadingBackend(true);

    fetch(`${backendUrl}/api/v1/cases`)
      .then((res) => {
        if (!res.ok) throw new Error("Fallback to /api/cases");
        return res.json();
      })
      .catch(() =>
        fetch(`${backendUrl}/api/cases`).then((r) => (r.ok ? r.json() : { cases: [] }))
      )
      .then((data) => {
        if (isMounted) {
          setBackendCases(data.cases || []);
          setLoadingBackend(false);
        }
      })
      .catch(() => {
        if (isMounted) setLoadingBackend(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, backendUrl]);

  if (!isOpen) return null;

  // Merge local session runs with backend repository cases
  const mergedCases = [
    ...localHistory.map((item) => ({
      ...item,
      isLocalSession: true,
    })),
    ...backendCases
      .filter((bc) => !localHistory.some((lh) => lh.case_id === bc.case_id))
      .map((bc) => ({
        case_id: bc.case_id,
        scenario_name: classifyScenario(
          {
            amount: bc.amount,
            counterparty_country: bc.counterparty_country,
            origin_country: bc.origin_country,
            destination_country: bc.destination_country,
            memo: bc.memo,
            counterparty_name: bc.counterparty_name || bc.scenario_name,
          },
          {
            preliminary_risk_level: bc.risk_level || bc.preliminary_risk_level,
            disposition_title:
              bc.disposition_title ||
              (bc.category === "untrusted_instructions"
                ? DISPOSITION.EMERGENCY
                : bc.amount > 10000
                ? DISPOSITION.ESCALATE
                : DISPOSITION.DISMISS),
          }
        ),
        amount: bc.amount,
        currency: bc.currency || "USD",
        category: bc.category,
        timestamp: bc.timestamp || new Date().toISOString(),
        disposition_title:
          bc.category === "untrusted_instructions"
            ? DISPOSITION.EMERGENCY
            : bc.amount > 10000
            ? DISPOSITION.ESCALATE
            : DISPOSITION.DISMISS,
        isLocalSession: false,
      })),
  ];

  // Filter cases based on search and disposition selector
  const filteredCases = mergedCases.filter((item) => {
    const matchesSearch =
      (item.case_id || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.scenario_name || "").toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    if (filterDisposition === "ALL") return true;
    if (filterDisposition === "DISMISS")
      return item.disposition_title === DISPOSITION.DISMISS;
    if (filterDisposition === "ESCALATE")
      return item.disposition_title === DISPOSITION.ESCALATE;
    if (filterDisposition === "EMERGENCY")
      return item.disposition_title === DISPOSITION.EMERGENCY;

    return true;
  });

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
                onClick={onClearLocalHistory}
                className="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors"
                title="Clear current session history"
              >
                <Trash2 className="w-3 h-3" />
                Clear Session
              </button>
            )}
          </div>
        </div>

        {/* Cases List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 divide-y divide-slate-800/40">
          {loadingBackend && mergedCases.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs font-mono">
              <RotateCcw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-400" />
              Loading compliance cases from repository...
            </div>
          ) : filteredCases.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs">
              No matching investigation cases found.
            </div>
          ) : (
            filteredCases.map((item, idx) => (
              <div
                key={`${item.case_id}-${idx}`}
                onClick={() => {
                  onSelectCase(item);
                  onClose();
                }}
                className="pt-3 first:pt-0 group p-3 rounded-xl border border-transparent hover:border-slate-800 hover:bg-slate-900/60 transition-all cursor-pointer"
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
                    </div>
                    <div className="text-xs text-slate-300 font-medium line-clamp-1">
                      {item.scenario_name}
                    </div>
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
              </div>
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
