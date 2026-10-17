"""
Data schemas and contracts for Ceylix AI.
All data structures are strictly typed using Pydantic.
Includes synthetic data provenance indicators and claim-level validation contracts.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, model_validator


from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, model_validator


EvidenceProvenanceType = Literal[
    "REAL_EXTERNAL",
    "LOCAL_DETERMINISTIC_FIXTURE",
    "SYNTHETIC_BENCHMARK",
    "SIMULATED",
    "DATA_UNAVAILABLE"
]

VerificationState = Literal[
    "VERIFIED",
    "UNVERIFIED",
    "UNKNOWN",
    "UNAVAILABLE",
    "MATCHED",
    "CLEAR",
    "NOT_APPLICABLE",
    "SIMULATED",
    "ERROR"
]

OperationalDisposition = Literal[
    "FAST_PATH_APPROVED",
    "RELEASE_WITH_PROVENANCE",
    "RELEASE_QUALIFIED",
    "ANALYST_REVIEW",
    "ANALYST_REVIEW_INPUT_MISMATCH",
    "ANALYST_REVIEW_EVIDENCE_INCOMPLETE",
    "ESCALATE_SANCTIONS_REVIEW",
    "BLOCKED_BY_POLICY",
    "ABSTAIN_FOR_HUMAN_REVIEW"
]


class EvidenceRecord(BaseModel):
    """A discrete verifiable evidence record with exact case ownership and provenance."""
    evidence_id: str = Field(description="Unique identifier for the evidence record")
    evidence_type: Literal[
        "KYC_PROFILE",
        "ACCOUNT_HISTORY",
        "DEVICE_IP_TELEMETRY",
        "SANCTIONS_PEP_SCREENING",
        "COUNTERPARTY_REPUTATION",
        "TERMINAL_LOCATION_LOG",
        "INVOICE_RECEIPT"
    ] = Field(description="Type of evidence")
    case_id: Optional[str] = Field(default=None, description="Bound investigation case identifier")
    transaction_id: Optional[str] = Field(default=None, description="Bound transaction reference")
    customer_id: Optional[str] = Field(default=None, description="Bound customer identifier")
    timestamp: str = Field(description="ISO-8601 observation timestamp when event was recorded")
    retrieval_timestamp: Optional[str] = Field(default=None, description="ISO-8601 timestamp when evidence was fetched")
    source_system: str = Field(description="Source system or database name")
    source_version: Optional[str] = Field(default=None, description="Watchlist or provider feed version")
    provenance_type: EvidenceProvenanceType = Field(
        default="SYNTHETIC_BENCHMARK",
        description="Origin classification: live external, local fixture, or synthetic benchmark"
    )
    verification_status: VerificationState = Field(
        default="VERIFIED",
        description="Explicit observation verification state"
    )
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured evidence payload")
    is_synthetic: bool = Field(default=True, description="Provenance flag: all benchmark data is synthetic")


class Transaction(BaseModel):
    """Authoritative structured financial transaction under investigation."""
    transaction_id: str = Field(description="Unique transaction reference")
    timestamp: str = Field(description="ISO-8601 timestamp of transaction execution")
    account_id: str = Field(description="Originating account ID")
    customer_id: str = Field(description="Originating customer ID")
    amount: float = Field(description="Transaction amount in original currency", gt=0.0)
    currency: str = Field(default="USD", description="ISO-4217 currency code")
    channel: str = Field(description="Payment rail: WIRE, ONLINE_BANKING, MOBILE_APP, POS_CHIP, CARD_NOT_PRESENT")
    counterparty_account: str = Field(description="Beneficiary account reference")
    counterparty_name: str = Field(description="Beneficiary entity or personal name")
    counterparty_bank: str = Field(description="Beneficiary financial institution")
    counterparty_country: str = Field(description="Beneficiary country code (ISO 3166-1 alpha-2)")
    origin_country: Optional[str] = Field(default=None, description="Originating country code (ISO 3166-1 alpha-2)")
    destination_country: Optional[str] = Field(default=None, description="Destination country code (ISO 3166-1 alpha-2)")
    device_id: Optional[str] = Field(default=None, description="Device identifier if available")
    ip_address: Optional[str] = Field(default=None, description="Client IP address if available")
    location: Optional[str] = Field(default=None, description="Reported location string")
    memo: Optional[str] = Field(default=None, description="Customer-provided memo or payment reference")
    original_instruction: Optional[str] = Field(default=None, description="Preserved raw payment instruction before parsing")
    is_synthetic: bool = Field(default=True, description="Provenance flag: all benchmark data is synthetic")

    @model_validator(mode="after")
    def normalize_fields(self) -> "Transaction":
        if self.currency:
            self.currency = self.currency.strip().upper()
        if self.counterparty_country:
            self.counterparty_country = self.counterparty_country.strip().upper()
        if not self.origin_country:
            self.origin_country = "US"
        else:
            self.origin_country = self.origin_country.strip().upper()
        if not self.destination_country:
            self.destination_country = self.counterparty_country or "US"
        else:
            self.destination_country = self.destination_country.strip().upper()
        return self

    @property
    def amount_usd(self) -> float:
        """Normalized transaction amount in USD."""
        return float(self.amount)


class InvestigationRequest(BaseModel):
    """Investigation query and analyst control context."""
    user_query: Optional[str] = Field(default=None, description="Analyst natural-language prompt or inquiry")
    analysis_type: Literal["STANDARD", "STRICT", "SANCTIONS_FOCUSED", "DEEP_FORENSIC"] = Field(
        default="STANDARD",
        description="Scrutiny mode applied to investigation"
    )
    analyst_instructions: Optional[str] = Field(default=None, description="Explicit human analyst guidance")
    detected_intent: Optional[str] = Field(default=None, description="Classified intent")


class InvestigationCase(BaseModel):
    """Model input payload for an investigation case."""
    case_id: str = Field(description="Unique case identifier")
    category: Literal[
        "complete_consistent",
        "missing_evidence",
        "conflicting_evidence",
        "stale_evidence",
        "untrusted_instructions",
        "benign_and_suspicious_controls"
    ] = Field(description="Benchmark test case category")
    scenario_name: str = Field(description="Human-readable scenario title")
    description: str = Field(default="Investigation Case", description="Brief case background")
    is_synthetic: bool = Field(default=True, description="Provenance flag: synthetic case")
    synthetic_disclaimer: str = Field(
        default="SYNTHETIC BENCHMARK CASE - NOT REAL FINANCIAL RECORDS",
        description="Explicit synthetic data notice"
    )
    created_at: str = Field(default="2026-03-30T10:00:00Z", description="Case creation ISO-8601 timestamp")
    transaction: Transaction = Field(description="Authoritative transaction under investigation")
    request: Optional[InvestigationRequest] = Field(default=None, description="Optional investigation request envelope")
    evidence_records: List[EvidenceRecord] = Field(default_factory=list, description="Available evidence bundle")


class ExpectedOutcome(BaseModel):
    """Ground truth expected outcome kept separate from model inputs."""
    case_id: str = Field(description="Matches InvestigationCase.case_id")
    category: str = Field(description="Test case category")
    scenario_name: str = Field(description="Scenario name")
    ground_truth_risk: Literal["LOW", "MEDIUM", "HIGH"] = Field(description="True underlying risk level")
    is_usable: bool = Field(description="Whether the case has complete, fresh, uncorrupted evidence")
    expected_abstention: bool = Field(description="Whether the system should abstain or route for human review")
    expected_abstention_reasons: List[str] = Field(default_factory=list, description="Specific defect codes")
    required_evidence_types: List[str] = Field(default_factory=list, description="Evidence types required by policy")
    known_conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Documented evidence conflicts")
    stale_evidence_ids: List[str] = Field(default_factory=list, description="IDs of expired evidence records")
    has_untrusted_injection: bool = Field(default=False, description="Whether memo contains adversarial instructions")


class Claim(BaseModel):
    """Structured claim generated by LLM and validated by deterministic rules."""
    claim_id: str = Field(description="Identifier for the claim (e.g. claim-001)")
    text: str = Field(description="Natural language claim assertion")
    claim_type: Literal["factual_assertion", "rule_result", "risk_inference"] = Field(
        default="factual_assertion",
        description="Classification of the claim"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Referenced evidence record IDs backing this claim"
    )
    field_references: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Explicit field mappings (e.g. [{'evidence_id': 'EVID-001', 'field': 'amount', 'value': 12000}])"
    )
    support_status: Literal[
        "supported",
        "unsupported",
        "conflicting",
        "stale",
        "insufficient_evidence",
        "requires_human_review"
    ] = Field(default="supported", description="Verification status of the claim")
    review_required: bool = Field(default=False, description="Whether human review is required for this claim")
    validation_notes: Optional[str] = Field(default=None, description="Detailed validation rationale")


class RuleEvaluationResult(BaseModel):
    """Outcome of a transparent deterministic risk rule."""
    rule_name: str = Field(description="Name of the deterministic rule")
    rule_description: str = Field(description="Rule logic summary")
    dimension: Literal[
        "FINANCIAL_TRANSACTION_RISK",
        "SANCTIONS_WATCHLIST_RISK",
        "CUSTOMER_KYC_RISK",
        "BEHAVIORAL_VELOCITY_RISK",
        "DEVICE_NETWORK_RISK",
            "BANK_RISK",
            "DATA_QUALITY_INPUT_INTENT",
        "EVIDENCE_COMPLETENESS"
    ] = Field(default="FINANCIAL_TRANSACTION_RISK", description="Separated risk dimension")
    passed: bool = Field(description="True if rule passed without risk, False if risk condition triggered")
    flagged: bool = Field(description="True if risk flag was raised")
    details: str = Field(description="Observed value vs threshold")
    severity: Literal["LOW", "MEDIUM", "HIGH", "INFO"] = Field(default="INFO")
    evidence_ids: List[str] = Field(default_factory=list, description="Supporting evidence IDs for the rule")


class RiskDimensionBreakdown(BaseModel):
    """Multi-dimensional risk score breakdown preventing premature dimension collapse."""
    financial_transaction_risk: Dict[str, Any] = Field(default_factory=dict)
    sanctions_watchlist_risk: Dict[str, Any] = Field(default_factory=dict)
    customer_kyc_risk: Dict[str, Any] = Field(default_factory=dict)
    behavioral_velocity_risk: Dict[str, Any] = Field(default_factory=dict)
    device_network_risk: Dict[str, Any] = Field(default_factory=dict)
    bank_risk: Dict[str, Any] = Field(default_factory=dict)
    data_quality_input_intent: Dict[str, Any] = Field(default_factory=dict)
    evidence_completeness_confidence: Dict[str, Any] = Field(default_factory=dict)


class InvestigationReport(BaseModel):
    """Complete authoritative investigation report."""
    case_id: str = Field(description="Reference to investigated case")
    workflow_type: Literal["baseline_unvalidated", "validated_deterministic"] = Field(
        default="validated_deterministic",
        description="Workflow architecture used"
    )
    workflow: Optional[str] = Field(
        default="validated_deterministic",
        description="Convenience alias for workflow_type"
    )
    fast_path_used: bool = Field(
        default=False,
        description="Whether the validated workflow completed via the deterministic System-1 fast path"
    )
    summary: str = Field(description="Executive case summary")
    preliminary_risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(description="Determined authoritative risk level")
    claims: List[Claim] = Field(default_factory=list, description="Claim breakdown")
    rule_results: List[RuleEvaluationResult] = Field(default_factory=list, description="Deterministic rule findings")
    risk_dimensions: Optional[RiskDimensionBreakdown] = Field(default=None, description="Multi-dimensional risk breakdown")
    abstain_recommended: bool = Field(description="Whether the report abstains from automated clearance")
    decision: OperationalDisposition = Field(description="Final operational disposition")
    sar_recommendation: bool = Field(default=False, description="Whether SAR filing is recommended (strictly separate from operational hold)")
    sar_rationale: Optional[str] = Field(default=None, description="Regulatory rationale for SAR recommendation")
    grounding_status: Literal["FULLY_GROUNDED", "PARTIALLY_GROUNDED", "UNGROUNDED"] = Field(
        default="FULLY_GROUNDED",
        description="Substantive evidence grounding status"
    )
    abstention_reasons: List[str] = Field(default_factory=list, description="Specific defect or escalation reasons")
    warnings: List[str] = Field(default_factory=list, description="Advisory notices")
    latency_ms: float = Field(default=0.0, description="Total workflow processing time in milliseconds")
    timestamp: str = Field(description="Timestamp of report generation")
    input_intent: Optional[str] = Field(default="TRANSACTION_INVESTIGATION", description="Input intent classification")
    routing_action: Optional[str] = Field(default=None, description="Workflow routing recommendation")
    telemetry_probes: Optional[Dict[str, Any]] = Field(default=None, description="Deterministic telemetry probe execution statuses")
    anomaly_score: Optional[float] = Field(default=None, description="Experimental novel-threat multivariate anomaly score")
    anomaly_details: Optional[Dict[str, Any]] = Field(default=None, description="Novel-threat detector feature breakdown")

    @model_validator(mode="before")
    @classmethod
    def populate_workflow_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "workflow" in data and "workflow_type" not in data:
                data["workflow_type"] = data["workflow"]
            if "workflow_type" in data and not data.get("workflow"):
                data["workflow"] = data["workflow_type"]
        return data
