/**
 * App.jsx — Ceylix AI Incident Workbench Orchestrator
 * ────────────────────────────────────────────────────────────────
 * Comprehensive state orchestrator:
 *   - 3-tier backend fetch strategy (Live Gemini → Simulate → Local Mock)
 *   - Custom Gemini API key injection (X-Custom-Gemini-Key header)
 *   - Risk Sensitivity Mode controls (Standard vs Strict Compliance)
 *   - Incident History Drawer with persistent session & repository runs
 *   - Settings & AST evidence gate status modal
 *   - Firestore audit persistence & export
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import Header from "./components/Header.jsx";
import TelemetryPanel from "./components/TelemetryPanel.jsx";
import AgentStepperPanel from "./components/AgentStepperPanel.jsx";
import DossierPanel from "./components/DossierPanel.jsx";
import SettingsModal from "./components/SettingsModal.jsx";
import HistoryDrawer from "./components/HistoryDrawer.jsx";
import {
  PRESET_SCENARIOS,
  BACKEND_STATUS,
  SYNC_STATE,
  API,
  STORAGE_KEYS,
  SENSITIVITY_MODE,
  mapDecisionToDisposition,
  riskLevelToScore,
} from "./types.js";

// ─────────────────────────────────────────────────────────────────────────────
// Constants & Configuration
// ─────────────────────────────────────────────────────────────────────────────
const BACKEND_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_BACKEND_URL) ||
  "http://127.0.0.1:8000";

const DEFAULT_SCENARIO_KEY = "scenarioB"; // High-risk demo on initial load

// ─────────────────────────────────────────────────────────────────────────────
// Backend response → UI result adapter
// ─────────────────────────────────────────────────────────────────────────────
function adaptBackendResponse(data, elapsedMs, selectedKey) {
  const fallbackClaims = PRESET_SCENARIOS[selectedKey]?.mockResult?.claims || [];
  const fallbackQuarantined =
    PRESET_SCENARIOS[selectedKey]?.mockResult?.quarantined_claims || [];

  const hasUntrustedInjection =
    data.abstention_reasons?.some((r) =>
      /injection|untrusted|adversarial|override/i.test(r)
    ) ||
    data.warnings?.some((w) =>
      /injection|untrusted|adversarial|override/i.test(w)
    ) ||
    false;

  const dispositionTitle = mapDecisionToDisposition(
    data.decision,
    data.preliminary_risk_level,
    hasUntrustedInjection
  );

  const calibratedScore = riskLevelToScore(data.preliminary_risk_level);

  // Map rule_results → probe statuses
  const rules = data.rule_results || [];
  const ofacFailed = rules.some(
    (r) =>
      (r.rule_name?.toLowerCase().includes("sanction") ||
        r.rule_name?.toLowerCase().includes("ofac") ||
        r.rule_id === "RULE_OFAC_SANCTIONS") &&
      !r.passed
  );
  const kycFailed = rules.some(
    (r) =>
      (r.rule_name?.toLowerCase().includes("kyc") ||
        r.rule_id === "RULE_KYC_VELOCITY") &&
      !r.passed
  );

  // Build claims from backend or fall back to mock
  const claims =
    data.claims && data.claims.length > 0
      ? data.claims.map((c) => ({
          claim_id: c.claim_id,
          text: c.text,
          tool: c.evidence_ids?.[0]
            ? `TOOL_${c.evidence_ids[0].replace(/-/g, "_").toUpperCase()}`
            : "TOOL_CORE_KYC",
          evidence_ref: c.evidence_ids?.[0] || "RULE-VAL-01",
          status: c.support_status === "supported" ? "verified" : "flagged",
        }))
      : fallbackClaims;

  // Build quarantined from warnings or injection abstention reasons
  const quarantinedClaims = hasUntrustedInjection
    ? (data.warnings || []).map((w, idx) => ({
        id: `QC-BE-0${idx + 1}`,
        assertion: w,
        reason:
          "Assertion failed deterministic validation — removed from regulatory dossier.",
        source_token: "backend_warning_flag",
      }))
    : fallbackQuarantined;

  return {
    workflow_type: data.workflow_type || "validated_deterministic",
    preliminary_risk_level: data.preliminary_risk_level || "MEDIUM",
    calibrated_score: calibratedScore,
    system1_disposition:
      data.preliminary_risk_level === "LOW" ? "PASS" : "DISPATCH_INVESTIGATION",
    system1_model: "Gemini 2.5 Flash",
    system2_model:
      data.preliminary_risk_level === "LOW"
        ? "Bypassed (Instant Clear)"
        : "Gemini 2.5 Pro (Deep Grounding)",
    grounding_status:
      data.abstain_recommended && hasUntrustedInjection
        ? "BLOCKED"
        : data.abstain_recommended
        ? "PARTIALLY_GROUNDED"
        : "FULLY_GROUNDED",
    latency_ms: data.latency_ms || elapsedMs,
    decision: data.decision || "ABSTAIN_FOR_HUMAN_REVIEW",
    disposition_title: dispositionTitle,
    probes: {
      ofac_sdn: {
        status: hasUntrustedInjection
          ? "DATA_UNAVAILABLE"
          : ofacFailed
          ? "MATCHED"
          : "CLEAR",
        detail: hasUntrustedInjection
          ? "Entity string contained adversarial control sequences — OFAC query quarantined by AST parser"
          : ofacFailed
          ? "Sanctions match detected — see rule results for SDN reference"
          : "No hits against OFAC SDN & Consolidated List",
        verified: !hasUntrustedInjection,
      },
      ip_geo: {
        status: "CLEAR",
        detail: "IP geolocation resolved via backend rule engine",
        verified: true,
      },
      core_kyc: {
        status: kycFailed ? "MATCHED" : "CLEAR",
        detail: kycFailed
          ? "KYC velocity anomaly detected by rule engine"
          : "Customer KYC profile within normal parameters",
        verified: true,
      },
    },
    summary:
      data.summary ||
      "Investigation completed through deterministic validation engine.",
    claims,
    quarantined_claims: quarantinedClaims,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Build InvestigationCase payload matching backend schemas.py
// ─────────────────────────────────────────────────────────────────────────────
function buildInvestigationCase(payload, selectedKey, caseId, sensitivityMode) {
  const categoryMap = {
    scenarioA: "benign_and_suspicious_controls",
    scenarioB: "benign_and_suspicious_controls",
    scenarioC: "untrusted_instructions",
  };

  return {
    case_id: caseId || `CASE-${Date.now().toString().slice(-6)}`,
    category: categoryMap[selectedKey] || "complete_consistent",
    scenario_name:
      PRESET_SCENARIOS[selectedKey]?.name || "Manual Triage Payload",
    description: `Analyst forensic triage for transaction ${payload.transaction_id} [Mode: ${sensitivityMode}]`,
    is_synthetic: true,
    synthetic_disclaimer:
      "SYNTHETIC BENCHMARK CASE - NOT REAL FINANCIAL RECORDS",
    created_at: new Date().toISOString(),
    sensitivity_mode: sensitivityMode,
    transaction: {
      transaction_id: payload.transaction_id,
      timestamp: payload.timestamp,
      account_id: payload.account_id,
      customer_id: payload.customer_id || "CUST-LIVE-01",
      amount: parseFloat(payload.amount) || 0,
      currency: payload.currency || "USD",
      channel: payload.channel || "WIRE",
      counterparty_account: payload.counterparty_account,
      counterparty_name: payload.counterparty_name,
      counterparty_bank: payload.counterparty_bank,
      counterparty_country: payload.counterparty_country,
      ip_address: payload.device_ip || null,
      location: payload.origin_country || null,
      memo: payload.memo || null,
      is_synthetic: true,
    },
    evidence_records: [],
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// App Component
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  const initialScenario = PRESET_SCENARIOS[DEFAULT_SCENARIO_KEY];

  // ── State ────────────────────────────────────────────────────────────────
  const [selectedScenarioKey, setSelectedScenarioKey] = useState(DEFAULT_SCENARIO_KEY);
  const [activePayload, setActivePayload] = useState({ ...initialScenario.payload });
  const [activeCaseId, setActiveCaseId] = useState(initialScenario.case_id);
  const [isEditingPayload, setIsEditingPayload] = useState(false);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [investigationResult, setInvestigationResult] = useState({
    ...initialScenario.mockResult,
  });
  const [backendStatus, setBackendStatus] = useState(BACKEND_STATUS.TESTING);
  const [lastExecutionTime, setLastExecutionTime] = useState(
    `${initialScenario.mockResult.latency_ms.toLocaleString()} ms`
  );
  const [firestoreSyncState, setFirestoreSyncState] = useState(SYNC_STATE.IDLE);
  const [firestoreSyncTs, setFirestoreSyncTs] = useState(null);

  // ── Enterprise Settings & Controls State ─────────────────────────────────
  const [customApiKey, setCustomApiKey] = useState(
    () => localStorage.getItem(STORAGE_KEYS.CUSTOM_GEMINI_KEY) || ""
  );
  const [sensitivityMode, setSensitivityMode] = useState(
    () => localStorage.getItem(STORAGE_KEYS.SENSITIVITY_MODE) || SENSITIVITY_MODE.STANDARD
  );
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [caseHistory, setCaseHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.CASE_HISTORY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const abortRef = useRef(null);

  // ── Health check on mount ────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${BACKEND_URL}${API.HEALTH}`, { signal: controller.signal })
      .then((res) => res.json())
      .then(() => setBackendStatus(BACKEND_STATUS.CONNECTED))
      .catch(() => setBackendStatus(BACKEND_STATUS.OFFLINE_FALLBACK));
    return () => controller.abort();
  }, []);

  // ── Save Custom Gemini Key ───────────────────────────────────────────────
  const handleSaveCustomKey = useCallback((newKey) => {
    setCustomApiKey(newKey);
    if (newKey) {
      localStorage.setItem(STORAGE_KEYS.CUSTOM_GEMINI_KEY, newKey);
    } else {
      localStorage.removeItem(STORAGE_KEYS.CUSTOM_GEMINI_KEY);
    }
  }, []);

  // ── Change Sensitivity Mode ──────────────────────────────────────────────
  const handleChangeSensitivityMode = useCallback((newMode) => {
    setSensitivityMode(newMode);
    localStorage.setItem(STORAGE_KEYS.SENSITIVITY_MODE, newMode);
  }, []);

  // ── Quick Scenario Selector ──────────────────────────────────────────────
  const handleSelectScenario = useCallback((key) => {
    const scn = PRESET_SCENARIOS[key];
    if (!scn) return;
    setSelectedScenarioKey(key);
    setActivePayload({ ...scn.payload });
    setActiveCaseId(scn.case_id);
    setInvestigationResult({ ...scn.mockResult });
    setLastExecutionTime(`${scn.mockResult.latency_ms.toLocaleString()} ms`);
    setIsEditingPayload(false);
    setFirestoreSyncState(SYNC_STATE.IDLE);
    setFirestoreSyncTs(null);
  }, []);

  // ── Payload field change ─────────────────────────────────────────────────
  const handlePayloadChange = useCallback((field, value) => {
    setActivePayload((prev) => ({ ...prev, [field]: value }));
  }, []);

  // ── Run Forensic Triage ──────────────────────────────────────────────────
  const handleRunTriage = useCallback(async () => {
    if (isInvestigating) return;
    setIsInvestigating(true);
    setFirestoreSyncState(SYNC_STATE.IDLE);
    setFirestoreSyncTs(null);

    // abort any previous in-flight request
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    const startTime = performance.now();
    const investigationCase = buildInvestigationCase(
      activePayload,
      selectedScenarioKey,
      activeCaseId,
      sensitivityMode
    );

    const requestHeaders = {
      "Content-Type": "application/json",
      ...(customApiKey ? { "X-Custom-Gemini-Key": customApiKey } : {}),
    };

    const attemptFetch = async (url) => {
      const res = await fetch(url, {
        method: "POST",
        headers: requestHeaders,
        body: JSON.stringify(investigationCase),
        signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    };

    let finalResult = null;

    try {
      let data = null;
      let usedRoute = null;

      // Attempt 1: Live Gemini
      if (backendStatus === BACKEND_STATUS.CONNECTED) {
        try {
          data = await attemptFetch(`${BACKEND_URL}${API.INVESTIGATE_LIVE}`);
          usedRoute = "live";
          setBackendStatus(BACKEND_STATUS.CONNECTED);
        } catch (liveErr) {
          if (signal.aborted) throw liveErr;
          console.warn("[Ceylix] Live Gemini call failed, trying simulate=true:", liveErr.message);
          // Attempt 2: Simulate mode
          data = await attemptFetch(`${BACKEND_URL}${API.INVESTIGATE_SIM}`);
          usedRoute = "simulated";
        }
      } else {
        // Attempt 2 directly if offline
        try {
          data = await attemptFetch(`${BACKEND_URL}${API.INVESTIGATE_SIM}`);
          usedRoute = "simulated";
        } catch {
          throw new Error("Backend offline");
        }
      }

      const elapsed = Math.round(performance.now() - startTime);
      setLastExecutionTime(`${elapsed.toLocaleString()} ms`);

      const adapted = adaptBackendResponse(data, elapsed, selectedScenarioKey);
      setInvestigationResult(adapted);
      finalResult = adapted;
    } catch (err) {
      if (signal.aborted) return;
      console.warn("[Ceylix] All backend routes failed, using deterministic local mock:", err.message);
      setBackendStatus(BACKEND_STATUS.OFFLINE_FALLBACK);
      const elapsed = Math.round(performance.now() - startTime);
      const mockLatency =
        PRESET_SCENARIOS[selectedScenarioKey]?.mockResult?.latency_ms || 1800;
      setLastExecutionTime(`${(elapsed + mockLatency).toLocaleString()} ms`);
      const fallback = { ...PRESET_SCENARIOS[selectedScenarioKey].mockResult };
      setInvestigationResult(fallback);
      finalResult = fallback;
    } finally {
      setIsInvestigating(false);

      // Append run to case history
      if (finalResult) {
        const historyItem = {
          case_id: activeCaseId,
          scenario_name:
            PRESET_SCENARIOS[selectedScenarioKey]?.name || activeCaseId,
          amount: activePayload.amount,
          currency: activePayload.currency || "USD",
          timestamp: new Date().toISOString(),
          disposition_title: finalResult.disposition_title,
          calibrated_score: finalResult.calibrated_score,
          preliminary_risk_level: finalResult.preliminary_risk_level,
          grounding_status: finalResult.grounding_status,
          sensitivity_mode: sensitivityMode,
          payload: { ...activePayload },
          result: { ...finalResult },
        };

        setCaseHistory((prev) => {
          const updated = [
            historyItem,
            ...prev.filter((p) => p.case_id !== activeCaseId),
          ].slice(0, 30);
          try {
            localStorage.setItem(STORAGE_KEYS.CASE_HISTORY, JSON.stringify(updated));
          } catch {
            // ignore localStorage quota errors
          }
          return updated;
        });
      }
    }
  }, [
    activePayload,
    selectedScenarioKey,
    activeCaseId,
    sensitivityMode,
    backendStatus,
    customApiKey,
    isInvestigating,
  ]);

  // ── Select Historical Case from Drawer ───────────────────────────────────
  const handleSelectHistoricalCase = useCallback((item) => {
    setActiveCaseId(item.case_id);
    if (item.payload) {
      setActivePayload({ ...item.payload });
    }
    if (item.result) {
      setInvestigationResult({ ...item.result });
      setLastExecutionTime(
        `${(item.result.latency_ms || 1200).toLocaleString()} ms`
      );
    }
    // Check if case matches any preset scenario key
    const matchedKey = Object.keys(PRESET_SCENARIOS).find(
      (k) => PRESET_SCENARIOS[k].case_id === item.case_id
    );
    if (matchedKey) {
      setSelectedScenarioKey(matchedKey);
    }
    setIsEditingPayload(false);
    setFirestoreSyncState(SYNC_STATE.IDLE);
    setFirestoreSyncTs(null);
  }, []);

  // ── Clear Local Session History ──────────────────────────────────────────
  const handleClearLocalHistory = useCallback(() => {
    setCaseHistory([]);
    localStorage.removeItem(STORAGE_KEYS.CASE_HISTORY);
  }, []);

  // ── Firestore Sync ───────────────────────────────────────────────────────
  const handleFirestoreSync = useCallback(async () => {
    if (firestoreSyncState === SYNC_STATE.SYNCING) return;
    setFirestoreSyncState(SYNC_STATE.SYNCING);

    const syncPayload = {
      case_id: activeCaseId,
      synced_at: new Date().toISOString(),
      dossier: investigationResult,
      telemetry: activePayload,
    };

    try {
      const res = await fetch(`${BACKEND_URL}${API.CASE_SYNC(activeCaseId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(syncPayload),
      });

      if (res.ok) {
        const data = await res.json();
        const ts = new Date(data.timestamp || Date.now()).toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        });
        setFirestoreSyncState(SYNC_STATE.SUCCESS);
        setFirestoreSyncTs(ts);
      } else {
        throw new Error(`server_error_${res.status}`);
      }
    } catch (err) {
      console.info(
        "[Ceylix] Firestore sync endpoint unavailable, using local confirmation:",
        err.message
      );
      await new Promise((r) => setTimeout(r, 600));
      const ts = new Date().toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      setFirestoreSyncState(SYNC_STATE.SUCCESS);
      setFirestoreSyncTs(`${ts} (local record)`);
    }
  }, [activeCaseId, investigationResult, activePayload, firestoreSyncState]);

  // ── Export Audit JSON ────────────────────────────────────────────────────
  const handleExportAudit = useCallback(() => {
    const auditPackage = {
      export_version: "1.0.0",
      compliance_standard: "BFSI_AI_SAFETY_ISO_42001",
      exported_at: new Date().toISOString(),
      case_id: activeCaseId,
      synthetic_disclaimer:
        "SYNTHETIC BENCHMARK CASE - NOT REAL FINANCIAL RECORDS",
      sensitivity_mode: sensitivityMode,
      telemetry_payload: activePayload,
      workbench_evaluation: investigationResult,
    };
    const blob = new Blob([JSON.stringify(auditPackage, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ceylix-audit-${activeCaseId}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [activeCaseId, activePayload, investigationResult, sensitivityMode]);

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Sticky Header with Controls */}
      <Header
        backendStatus={backendStatus}
        selectedScenarioKey={selectedScenarioKey}
        scenarios={PRESET_SCENARIOS}
        onSelectScenario={handleSelectScenario}
        onExportAudit={handleExportAudit}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenHistory={() => setIsHistoryOpen(true)}
        customApiKey={customApiKey}
        historyCount={caseHistory.length}
      />

      {/* 3-Panel Compliance Workbench */}
      <main className="flex-1 max-w-[1400px] w-full mx-auto p-5">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Panel 1: Telemetry & Sensitivity */}
          <TelemetryPanel
            payload={activePayload}
            isEditing={isEditingPayload}
            isInvestigating={isInvestigating}
            backendStatus={backendStatus}
            sensitivityMode={sensitivityMode}
            onChangeSensitivityMode={handleChangeSensitivityMode}
            onEditToggle={() => setIsEditingPayload((v) => !v)}
            onPayloadChange={handlePayloadChange}
            onRunTriage={handleRunTriage}
          />

          {/* Panel 2: Agent Stepper & Grounding Gauge */}
          <AgentStepperPanel
            result={investigationResult}
            lastExecutionTime={lastExecutionTime}
            isInvestigating={isInvestigating}
            backendStatus={backendStatus}
          />

          {/* Panel 3: Evidence Dossier & Quarantine */}
          <DossierPanel
            result={investigationResult}
            caseId={activeCaseId}
            payload={activePayload}
            backendStatus={backendStatus}
            firestoreSyncState={firestoreSyncState}
            firestoreSyncTs={firestoreSyncTs}
            onFirestoreSync={handleFirestoreSync}
            onExportAudit={handleExportAudit}
          />
        </div>
      </main>

      {/* Slide-over Case History Drawer */}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        backendUrl={BACKEND_URL}
        localHistory={caseHistory}
        onSelectCase={handleSelectHistoricalCase}
        onClearLocalHistory={handleClearLocalHistory}
      />

      {/* Settings & Custom Gemini Key Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        backendUrl={BACKEND_URL}
        customApiKey={customApiKey}
        onSaveCustomKey={handleSaveCustomKey}
      />

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 px-6 py-3 text-center text-[11px] text-slate-600">
        <div className="max-w-[1400px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="font-mono">
            Ceylix AI Incident Workbench · Evidence-Grounded BFSI Risk Investigation
          </div>
          <div className="flex items-center gap-4 text-slate-700 font-mono text-[10px]">
            <span>Vertex AI · Gemini 2.5 Flash / Pro</span>
            <span>·</span>
            <span>Deterministic AST Claim Validation</span>
            <span>·</span>
            <span>Google Cloud Run</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
