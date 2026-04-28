"""
classifier.py — Core AI pipeline for MumzSupport AI
Handles intent classification, urgency detection, reply generation (EN + AR)
"""

import os
import json
import re
import httpx
from typing import Optional
from pydantic import BaseModel, field_validator

# ─── Output Schema ────────────────────────────────────────────────────────────

class SupportResponse(BaseModel):
    intent: str                  # refund | exchange | complaint | query | unknown
    urgency: str                 # low | medium | high | unknown
    confidence: float            # 0.0 – 1.0
    reply_en: str                # English reply
    reply_ar: str                # Arabic reply (native, not literal)
    reasoning: str               # why this classification was made
    needs_escalation: bool       # flag for human handoff
    uncertainty_note: Optional[str] = None  # populated when model is unsure

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, v):
        allowed = {"refund", "exchange", "complaint", "query", "unknown"}
        if v not in allowed:
            return "unknown"
        return v

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v):
        allowed = {"low", "medium", "high", "unknown"}
        if v not in allowed:
            return "unknown"
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))


# ─── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a customer support AI assistant for Mumzworld — the largest e-commerce 
platform for mothers and babies in the Middle East. You process customer emails and classify them.

CLASSIFICATION RULES:
- intent must be exactly one of: refund, exchange, complaint, query, unknown
  - refund: customer wants money back or cancellation
  - exchange: customer wants a different item, size, colour
  - complaint: customer is unhappy about service, product quality, delivery, or experience
  - query: question about order status, product info, availability, shipping, policies
  - unknown: email is too ambiguous to classify with confidence

- urgency must be exactly one of: low, medium, high, unknown
  - high: safety concern, medical product issue, very angry customer, time-sensitive (delivery today)
  - medium: clear frustration, order delay, wrong item received
  - low: general question, casual inquiry

- confidence: a decimal between 0.0 and 1.0
  - Below 0.5 → set intent to "unknown", populate uncertainty_note
  - If the email is not in English or Arabic, or is gibberish → intent: "unknown", confidence: 0.1

REPLY RULES:
- reply_en: Write a warm, helpful, professional reply in natural English. 
  Address the specific concern. Do NOT promise things you cannot guarantee.
  Do NOT reveal internal systems. Use the mother's name if present.
  If intent is unknown, ask a clarifying question.

- reply_ar: Write the SAME reply in natural Gulf Arabic (not MSA, not literal translation).
  Use warm, colloquial tone appropriate for a GCC mother. 
  "أهلاً وسهلاً" style openings, not formal bureaucratic Arabic.

- needs_escalation: true if urgency is high, or if the issue involves product safety, 
  medical concerns, or the customer has expressed intent to leave a negative review publicly.

- reasoning: 1-2 sentences explaining your classification decision.

CRITICAL: You must respond ONLY with valid JSON matching the schema exactly. No markdown, no explanation outside JSON."""


# ─── Prompt Builder ─────────────────────────────────────────────────────────────

def build_user_prompt(email_text: str) -> str:
    return f"""Analyse this customer email and respond with JSON only.

CUSTOMER EMAIL:
\"\"\"
{email_text.strip()}
\"\"\"

Respond with this exact JSON schema:
{{
  "intent": "refund|exchange|complaint|query|unknown",
  "urgency": "low|medium|high|unknown",
  "confidence": 0.0-1.0,
  "reply_en": "...",
  "reply_ar": "...",
  "reasoning": "...",
  "needs_escalation": true|false,
  "uncertainty_note": "..." or null
}}"""


# ─── API Call ────────────────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def call_llm(email_text: str, api_key: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> dict:
    """
    Calls OpenRouter with the email. Returns raw JSON dict from the model.
    Falls back gracefully on API errors.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mumzworld-ai-support.demo",
        "X-Title": "MumzSupport AI"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(email_text)}
        ],
        "temperature": 0.1,     # low temp for consistent classification
        "max_tokens": 1000,
        "response_format": {"type": "json_object"}
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    raw_content = data["choices"][0]["message"]["content"]

    # Strip markdown fences if present
    clean = raw_content.strip()
    if clean.startswith("```"):
        clean = re.sub(r"```(?:json)?", "", clean).strip().rstrip("```").strip()

    return json.loads(clean)


# ─── Main Classify Function ───────────────────────────────────────────────────

def classify_email(email_text: str, api_key: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> SupportResponse:
    """
    Public interface. Takes raw email text, returns validated SupportResponse.
    Handles all failure modes explicitly — never silently returns garbage.
    """
    if not email_text or not email_text.strip():
        return SupportResponse(
            intent="unknown",
            urgency="unknown",
            confidence=0.0,
            reply_en="We received an empty message. Could you describe how we can help you today?",
            reply_ar="وصلنا رسالتك فارغة. هل يمكنك إخبارنا كيف نساعدك؟",
            reasoning="Empty input provided.",
            needs_escalation=False,
            uncertainty_note="Input was empty or whitespace only."
        )

    if len(email_text.strip()) < 10:
        return SupportResponse(
            intent="unknown",
            urgency="unknown",
            confidence=0.1,
            reply_en="Thank you for reaching out! Could you share a bit more detail about your concern so we can assist you properly?",
            reply_ar="شكراً لتواصلك معنا! هل يمكنك إعطائنا تفاصيل أكثر حتى نقدر نساعدك؟",
            reasoning="Input too short to classify meaningfully.",
            needs_escalation=False,
            uncertainty_note="Email was too short (under 10 characters) to classify."
        )

    try:
        raw = call_llm(email_text, api_key, model)
        response = SupportResponse(**raw)
        return response

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Invalid API key. Please check your OpenRouter API key.") from e
        elif e.response.status_code == 429:
            raise ValueError("Rate limit hit. Please wait a moment and try again.") from e
        else:
            raise ValueError(f"API error {e.response.status_code}: {e.response.text}") from e

    except json.JSONDecodeError as e:
        # LLM returned non-JSON — surface this explicitly
        return SupportResponse(
            intent="unknown",
            urgency="unknown",
            confidence=0.0,
            reply_en="We're experiencing a technical issue. A team member will follow up shortly.",
            reply_ar="نواجه مشكلة تقنية حالياً. سيتواصل معك أحد أعضاء الفريق قريباً.",
            reasoning="Model returned malformed JSON — could not parse response.",
            needs_escalation=True,
            uncertainty_note=f"JSON parse error: {str(e)}"
        )

    except Exception as e:
        return SupportResponse(
            intent="unknown",
            urgency="unknown",
            confidence=0.0,
            reply_en="We're having trouble processing your request right now. Please try again in a moment.",
            reply_ar="نواجه بعض الصعوبات في معالجة طلبك الآن. يرجى المحاولة مرة أخرى.",
            reasoning=f"Unexpected error: {str(e)}",
            needs_escalation=True,
            uncertainty_note=str(e)
        )
