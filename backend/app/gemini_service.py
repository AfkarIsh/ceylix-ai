"""
Gemini Service for Ceylix AI.
Integrates with Google Gemini via Google GenAI SDK (gemini-3.8-flash) or OpenRouter API.
Strict live production pipeline with deterministic JSON extraction.
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Tuple
import requests

try:
    from backend.app.schemas import (
        InvestigationCase,
        Claim,
        InvestigationReport,
    )
except ModuleNotFoundError:
    from app.schemas import (
        InvestigationCase,
        Claim,
        InvestigationReport,
    )

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "google/gemini-2.5-flash")
DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash"


def get_openrouter_model() -> str:
    """Return an OpenRouter-qualified Gemini model ID.

    Older deployments used unqualified or retired Gemini IDs such as
    ``gemini-2.0-flash``. OpenRouter requires provider-qualified IDs and no
    longer accepts that retired model name.
    """
    configured_model = os.environ.get("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
    legacy_models = {
        "gemini-2.0-flash",
        "google/gemini-2.0-flash",
    }
    if configured_model in legacy_models:
        return DEFAULT_OPENROUTER_MODEL
    if "/" not in configured_model:
        return f"google/{configured_model}"
    return configured_model


INVESTIGATION_SYSTEM_PROMPT = """You are Ceylix AI, an analyst assistant for financial transaction risk investigation.
Analyze the provided transaction and the available evidence bundle.
You must produce a concise structured JSON response adhering strictly to the schema below:

{
  "summary": "Concise factual summary of the transaction (max 2 sentences)",
  "preliminary_risk_level": "LOW" | "MEDIUM" | "HIGH",
  "abstain_recommended": true | false,
  "claims": [
    {
      "claim_id": "claim-001",
      "text": "Specific factual or risk statement",
      "claim_type": "factual_assertion" | "rule_result" | "risk_inference",
      "evidence_ids": ["EVID-001"],
      "field_references": [{"evidence_id": "EVID-001", "field": "amount", "value": 15000.0}],
      "support_status": "supported",
      "review_required": false
    }
  ]
}

Important Instructions:
- Provide at most 2-3 concise claims.
- Cite the exact evidence_ids backing each claim whenever possible.
- If evidence is missing, state what is observed.
- Return ONLY valid JSON, with no enclosing text or markdown formatting.
"""


def build_case_prompt(case: InvestigationCase) -> str:
    """Build the case input prompt."""
    tx = case.transaction
    prompt_lines = [
        f"INVESTIGATION CASE ID: {case.case_id}",
        f"SCENARIO: {case.scenario_name}",
        f"DESCRIPTION: {case.description}",
        "",
        "TRANSACTION DETAILS:",
        f"- Transaction ID: {tx.transaction_id}",
        f"- Timestamp: {tx.timestamp}",
        f"- Account ID: {tx.account_id}",
        f"- Customer ID: {tx.customer_id}",
        f"- Amount: {tx.amount:,.2f} {tx.currency}",
        f"- Channel: {tx.channel}",
        f"- Counterparty Name: {tx.counterparty_name}",
        f"- Counterparty Account: {tx.counterparty_account}",
        f"- Counterparty Bank: {tx.counterparty_bank}",
        f"- Counterparty Country: {tx.counterparty_country}",
        f"- Device ID: {tx.device_id or 'N/A'}",
        f"- IP Address: {tx.ip_address or 'N/A'}",
        f"- Location: {tx.location or 'N/A'}",
        f"- Memo / Notes: {tx.memo or 'N/A'}",
        "",
        "AVAILABLE EVIDENCE RECORDS:",
    ]

    if not case.evidence_records:
        prompt_lines.append("(No evidence records available in case bundle)")
    else:
        for idx, rec in enumerate(case.evidence_records, 1):
            prompt_lines.append(
                f"{idx}. Evidence ID: {rec.evidence_id} | Type: {rec.evidence_type} | Timestamp: {rec.timestamp} | Source: {rec.source_system}"
            )
            prompt_lines.append(f"   Data: {json.dumps(rec.data)}")

    prompt_lines.append("")
    prompt_lines.append("Generate the structured JSON report.")
    return "\n".join(prompt_lines)


def clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Extract and parse JSON safely from LLM output."""
    clean = raw_text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # 1. Match outermost curly braces
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        # 2. Try slicing up to last closing brace
        last_brace = clean.rfind("}")
        if last_brace != -1:
            first_brace = clean.find("{")
            if first_brace != -1 and first_brace < last_brace:
                try:
                    return json.loads(clean[first_brace:last_brace+1])
                except Exception:
                    pass
        raise


def call_gemini_api(
    case: InvestigationCase,
    custom_api_key: Optional[str] = None
) -> Tuple[Dict[str, Any], float]:
    """
    Call Gemini API directly via Google GenAI SDK or OpenRouter.
    Unconditionally executes live model inference.
    Raises ValueError or RuntimeError if API keys are missing or requests fail.
    Returns: (parsed_json, latency_seconds)
    """
    start_time = time.time()
    active_gemini_key = custom_api_key or GEMINI_API_KEY

    # 1. Direct Google GenAI API Call (Primary live pipeline)
    if active_gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=active_gemini_key)
            model_name = os.environ.get("GEMINI_MODEL") or os.environ.get("GEMINI_SDK_MODEL", "gemini-3.8-flash")
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=INVESTIGATION_SYSTEM_PROMPT
            )
            prompt = build_case_prompt(case)
            response = model.generate_content(prompt)
            parsed = clean_json_response(response.text)
            latency = time.time() - start_time
            return parsed, latency
        except Exception as e:
            # Re-raise live exception if OpenRouter is not available
            if not OPENROUTER_API_KEY:
                raise RuntimeError(f"Live Google GenAI call failed: {e}") from e
            print(f"[GeminiService] Primary Google GenAI call failed, trying OpenRouter: {e}")

    # 2. OpenRouter API Call (Secondary live fallback)
    if OPENROUTER_API_KEY:
        try:
            prompt = build_case_prompt(case)
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ceylix.ai",
                "X-Title": "Ceylix AI Risk Investigator",
            }
            payload = {
                "model": get_openrouter_model(),
                "messages": [
                    {"role": "system", "content": INVESTIGATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1200,
                "temperature": 0.0,
            }
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45.0
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = clean_json_response(content)
                latency = time.time() - start_time
                return parsed, latency
            else:
                raise RuntimeError(f"OpenRouter API returned HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            raise RuntimeError(f"Live OpenRouter call failed: {e}") from e

    raise ValueError(
        "No valid Gemini API key configured. Please set GEMINI_API_KEY in backend/.env "
        "or provide a key via the X-Custom-Gemini-Key request header."
    )
