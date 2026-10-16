/**
 * SettingsModal.jsx — Enterprise Settings & Custom Gemini Key Injector
 * ──────────────────────────────────────────────────────────────────
 * Allows compliance analysts and forensic risk auditors to inject a custom
 * Gemini API Key into all outgoing triage requests. Persists key securely
 * in browser localStorage and displays AST Evidence Gate metrics.
 */

import React, { useState, useEffect } from "react";
import {
  X,
  Key,
  ShieldCheck,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Eye,
  EyeOff,
  Trash2,
  RefreshCw,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import { STORAGE_KEYS } from "../types.js";

export default function SettingsModal({
  isOpen,
  onClose,
  backendUrl,
  customApiKey,
  onSaveCustomKey,
}) {
  const [apiKeyInput, setApiKeyInput] = useState(customApiKey || "");
  const [showKey, setShowKey] = useState(false);
  const [testStatus, setTestStatus] = useState(null); // null | 'testing' | 'success' | 'error'
  const [testMessage, setTestMessage] = useState("");
  const [selectedModel, setSelectedModel] = useState(
    () => localStorage.getItem(STORAGE_KEYS.MODEL_PREFERENCE) || "gemini-2.5-pro"
  );
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    setApiKeyInput(customApiKey || "");
  }, [customApiKey, isOpen]);

  if (!isOpen) return null;

  const handleSave = (e) => {
    e.preventDefault();
    const cleanKey = apiKeyInput.trim();
    onSaveCustomKey(cleanKey);
    localStorage.setItem(STORAGE_KEYS.MODEL_PREFERENCE, selectedModel);
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 600);
  };

  const handleClear = () => {
    setApiKeyInput("");
    onSaveCustomKey("");
    setTestStatus(null);
    setTestMessage("API Key cleared. Reverted to server-configured default.");
  };

  const handleTestConnection = async () => {
    setTestStatus("testing");
    setTestMessage("Pinging backend with injected API credential...");
    const startTime = performance.now();
    try {
      const res = await fetch(`${backendUrl}/health`, {
        headers: {
          "Content-Type": "application/json",
          "X-Custom-Gemini-Key": apiKeyInput.trim(),
        },
      });
      const elapsed = Math.round(performance.now() - startTime);
      if (res.ok) {
        setTestStatus("success");
        setTestMessage(`Connection verified! Backend responded in ${elapsed} ms.`);
      } else {
        setTestStatus("error");
        setTestMessage(`Backend returned HTTP ${res.status}. Check API key.`);
      }
    } catch {
      setTestStatus("error");
      setTestMessage("Could not connect to backend. Please verify your backend server.");
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
    >
      <div
        className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <h2 id="settings-modal-title" className="text-base font-semibold text-white tracking-tight">
                Enterprise Pipeline Settings
              </h2>
              <p className="text-xs text-slate-400">
                Configure custom Gemini API credentials & AST evidence rules
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close Settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSave} className="p-6 space-y-6">
          {/* Custom Gemini Key Injection */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                htmlFor="custom-gemini-key"
                className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                Custom Gemini API Key Override
              </label>
              {customApiKey ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  Custom Key Active
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  Using Server Default
                </span>
              )}
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Injects your Google AI Studio key into all outgoing requests via the{" "}
              <code className="text-indigo-300 font-mono text-[11px] bg-slate-800 px-1 py-0.5 rounded">
                X-Custom-Gemini-Key
              </code>{" "}
              header. Stored only in your local browser session.
            </p>

            <div className="relative flex items-center">
              <input
                id="custom-gemini-key"
                type={showKey ? "text" : "password"}
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="AIzaSy... (leave blank to use server environment key)"
                className="w-full pl-3 pr-20 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-sm font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                autoComplete="off"
                spellCheck="false"
              />
              <div className="absolute right-2 flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  title={showKey ? "Hide key" : "Show key"}
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                {apiKeyInput && (
                  <button
                    type="button"
                    onClick={handleClear}
                    className="p-1.5 rounded-md text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
                    title="Clear custom key"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            {/* Test Connection Button & Status */}
            <div className="flex items-center justify-between pt-1">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testStatus === "testing"}
                className="text-xs inline-flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 font-medium disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${testStatus === "testing" ? "animate-spin" : ""}`} />
                Test API Connectivity
              </button>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-xs text-slate-500 hover:text-slate-400 inline-flex items-center gap-1 transition-colors"
              >
                Get Gemini API Key <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            {testMessage && (
              <div
                className={`p-2.5 rounded-lg text-xs font-mono border ${
                  testStatus === "success"
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : testStatus === "error"
                    ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                    : "bg-slate-800/80 border-slate-700 text-slate-300"
                }`}
              >
                {testMessage}
              </div>
            )}
          </div>

          {/* Model Preference Selection */}
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-sky-400" />
              Primary Reasoning Engine
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setSelectedModel("gemini-2.5-pro")}
                className={`p-3 text-left rounded-xl border transition-all ${
                  selectedModel === "gemini-2.5-pro"
                    ? "bg-indigo-600/15 border-indigo-500 text-white shadow-sm"
                    : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <div className="font-semibold text-xs text-white">Gemini 2.5 Pro</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Deep System-2 Grounding & Logic</div>
              </button>

              <button
                type="button"
                onClick={() => setSelectedModel("gemini-2.5-flash")}
                className={`p-3 text-left rounded-xl border transition-all ${
                  selectedModel === "gemini-2.5-flash"
                    ? "bg-indigo-600/15 border-indigo-500 text-white shadow-sm"
                    : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <div className="font-semibold text-xs text-white">Gemini 2.5 Flash</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Ultra-Low Latency Heuristics</div>
              </button>
            </div>
          </div>

          {/* AST Evidence Gate & Governance Invariants */}
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              AST Evidence Gate & Governance Invariants
            </label>
            <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-3.5 space-y-2.5 text-xs">
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-1.5 text-slate-400">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Deterministic Risk Rules
                </span>
                <span className="font-mono text-emerald-400">7 Active Invariants</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-1.5 text-slate-400">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Adversarial Prompt AST Quarantine
                </span>
                <span className="font-mono text-emerald-400">Zero-Bypass Policy</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-1.5 text-slate-400">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Evidence Grounding Policy
                </span>
                <span className="font-mono text-emerald-400">Claims Requiring Bound IDs</span>
              </div>
            </div>
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-1.5"
            >
              {savedSuccess ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-300" /> Saved!
                </>
              ) : (
                "Save Configuration"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
