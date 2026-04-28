# MumzSupport AI 🍼

> **Mumzworld AI-Native Intern Assessment — Track A: AI Engineering Intern**  
> Customer support email triage system with intent classification, urgency detection, structured output, and bilingual replies (English + Arabic).

---

## One-Paragraph Summary

MumzSupport AI is a customer support triage assistant built for Mumzworld — the largest baby and mother e-commerce platform in the Middle East. It takes a raw customer email, classifies intent (refund / exchange / complaint / query / unknown), detects urgency (low / medium / high), generates a structured JSON response validated against a Pydantic schema, and produces a natural reply in both English and Gulf Arabic. It flags critical tickets (safety issues, PR threats) for immediate human escalation, and explicitly expresses uncertainty rather than hallucinating a confident answer.

---

## Quick Setup (under 5 minutes)

### Prerequisites
- Python 3.10+
- A free [OpenRouter](https://openrouter.ai) API key (no credit card required)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/mumzworld-mumsupport-ai
cd mumzworld-mumsupport-ai
pip install -r requirements.txt
```

### Run the demo UI

```bash
export OPENROUTER_API_KEY=your_key_here
streamlit run app.py
```

Open `http://localhost:8501` in your browser. Paste any customer email and click **Classify**.

### Run via Python (no UI)

```python
from src.classifier import classify_email

result = classify_email(
    "I received the wrong item in my order #MW-1234. I want a full refund.",
    api_key="your_openrouter_key"
)

print(result.intent)      # "refund"
print(result.urgency)     # "medium"
print(result.confidence)  # 0.95
print(result.reply_en)    # "Dear customer, we're sorry..."
print(result.reply_ar)    # "أهلاً وسهلاً، نأسف جداً..."
```

### Run evals

```bash
python evals.py --api-key your_key_here
# Results saved to evals/results.json
```

---

## Output Schema

Every response validates against this Pydantic model — failures are **explicit**, never silent:

```python
class SupportResponse(BaseModel):
    intent: str           # refund | exchange | complaint | query | unknown
    urgency: str          # low | medium | high | unknown
    confidence: float     # 0.0 – 1.0
    reply_en: str         # Natural English reply
    reply_ar: str         # Gulf Arabic reply (not literal translation)
    reasoning: str        # Why this classification was made
    needs_escalation: bool  # True → route to human agent immediately
    uncertainty_note: Optional[str]  # Populated when model is unsure
```

**Example output (TC-006 — expired formula safety case):**

```json
{
  "intent": "complaint",
  "urgency": "high",
  "confidence": 0.98,
  "reply_en": "Dear valued customer, we take this extremely seriously. Please stop using the formula immediately and consult your pediatrician as a precaution. We are arranging an urgent replacement and will have our quality team contact you within the hour. Order replacement is being prioritised now.",
  "reply_ar": "عزيزتنا، هذا الأمر يهمنا جداً وما نتهاون فيه. وقفي استخدام الحليب فوراً وراجعي طبيب الأطفال كإجراء احترازي. نحن بنرتب بديل عاجل وفريق الجودة راح يتواصل معكِ خلال ساعة.",
  "reasoning": "Expired baby formula fed to an infant is a safety-critical complaint requiring immediate escalation.",
  "needs_escalation": true,
  "uncertainty_note": null
}
```

---

## Project Structure

```
mumzworld-mumsupport-ai/
├── app.py                  # Streamlit demo UI
├── evals.py                # Evaluation harness
├── requirements.txt
├── README.md
├── EVALS.md                # Rubric, test cases, results, failure analysis
├── TRADEOFFS.md            # Problem selection, architecture, cuts
├── src/
│   └── classifier.py       # Core pipeline (prompt, API call, validation)
├── data/
│   └── test_emails.json    # 20 synthetic test emails (easy / medium / adversarial)
└── evals/
    └── results.json        # Last eval run output
```

---

## Evals

See **[EVALS.md](EVALS.md)** for the full rubric, all 20 test cases, scored results, and failure analysis.

**Summary (Llama 3.3 70B, free via OpenRouter):**

| Metric | Score |
|---|---|
| Overall pass rate | **19/20 (95%)** |
| Avg composite score | **0.962** |
| Safety escalation | **3/3 (100%)** |
| Easy cases | 5/5 |
| Medium cases | 8/8 |
| Adversarial cases | 6/7 |

The one failure (TC-012: "I am very unhappy. Fix it now!!!") is documented with root cause analysis in EVALS.md.

---

## Tradeoffs

See **[TRADEOFFS.md](TRADEOFFS.md)** for full discussion.

**TL;DR:**
- Prompt-based over fine-tuning: faster, maintainable, sufficient accuracy for a prototype
- Llama 3.3 70B (free): strong multilingual performance at zero cost
- Pydantic validation: explicit failures over silent corruption
- Low temperature (0.1): consistent classification over stylistic variation
- Cut: order API integration, agent loop with tool use, multi-turn conversation history

---

## Tooling

| Tool | Role |
|---|---|
| **OpenRouter** | Unified API gateway to free LLMs. Used Llama 3.3 70B for classification and reply generation. No credit card required. |
| **meta-llama/llama-3.3-70b-instruct:free** | Primary model. Strong instruction following and Arabic output quality. |
| **Pydantic v2** | Output schema validation. All model outputs are validated before being returned. |
| **httpx** | Async-capable HTTP client for OpenRouter API calls. |
| **Streamlit** | Demo UI. Chosen for fastest path from code to interactive prototype. |
| **Claude (claude.ai)** | Used for prompt iteration — testing edge cases, refining the system prompt, and reviewing Arabic reply quality. |

**How AI tools were used:**
- The system prompt went through ~6 iterations. Claude was used to red-team the prompt by simulating adversarial inputs and identifying where the model would hallucinate or under-specify.
- The Streamlit UI layout was scaffolded with Claude assistance, then customised manually for the Mumzworld aesthetic.
- All core logic (`classifier.py`, `evals.py`, scoring rubric) was written by hand and reviewed manually.
- Arabic reply quality was spot-checked using Claude to flag any MSA constructions that sounded unnatural in a Gulf context.

**What didn't work:**
- DeepSeek R1 occasionally produced verbose chain-of-thought reasoning inside the JSON output, breaking `json.loads`. Added a markdown fence stripper to handle this.
- An earlier prompt version without the `response_format: json_object` flag produced inconsistent JSON structure. Fixed by adding the format constraint and the `clean` stripping step in `call_llm`.

---

## Time Log

| Phase | Time |
|---|---|
| Problem scoping + architecture design | 45 min |
| System prompt engineering + iteration | 60 min |
| `classifier.py` core pipeline | 45 min |
| Synthetic dataset (20 test emails) | 30 min |
| `evals.py` harness + scoring logic | 45 min |
| Streamlit UI | 45 min |
| README + EVALS.md + TRADEOFFS.md | 30 min |
| **Total** | **~5 hrs 20 min** |

Went ~20 minutes over. The Arabic spot-checking and prompt iteration took longer than estimated.

---

## Uncertainty Handling

This is a first-class concern in the design, not an afterthought:

1. **Input-level guards** — Empty inputs and inputs < 10 characters return `unknown` before hitting the API.
2. **Confidence threshold** — If `confidence < 0.5`, `intent` is overridden to `unknown`. The reply asks for clarification.
3. **`uncertainty_note` field** — Populated with a human-readable explanation whenever the model is uncertain. Surfaced in UI and included in JSON.
4. **Explicit JSON parse failure** — If the model returns malformed JSON, we return a structured `unknown` response with `needs_escalation: true` rather than crashing.
5. **Escalation flag** — Safety, medical, and PR-threat cases trigger `needs_escalation: true` via the system prompt, not post-processing heuristics.

---

## AI Usage Note

- **OpenRouter + Llama 3.3 70B**: Core classification and bilingual reply generation
- **Claude (claude.ai)**: Prompt iteration, adversarial red-teaming, Arabic quality review
- **Streamlit**: UI scaffolding (then manually customised)
- All pipeline logic, evaluation harness, and scoring rubric written and reviewed by hand

---MumSupport AI – Intelligent Support Assistant for Mothers
📌 Problem

Mothers using Mumzworld often need quick, reliable answers to questions about:

Baby care
Products
Health & safety
Parenting guidance

However:

Searching manually is time-consuming
Support teams can be overloaded
Answers may not always be personalized

👉 There is a need for a smart, instant, and reliable AI assistant.

💡 Solution

MumSupport AI is an AI-powered assistant that provides:

Instant responses to parenting queries
Context-aware and helpful suggestions
Scalable support without human delay

It acts as a virtual assistant for mothers, improving both user experience and support efficiency.

✨ Features
💬 Natural language interaction
⚡ Instant AI-generated responses
🧠 Context-aware answers
🖥️ Simple and clean UI (Streamlit-based)
🔄 Scalable for real-world deployment

⚙️ How It Works
🔄 Flow
User Input → Streamlit UI → Backend Processing → LLM → Response → UI Display
🧠 Core Logic
User enters a query
Input is processed and sent to an LLM
The model generates a relevant response
Output is displayed in real-time
🏗️ Architecture (Conceptual)
Frontend: Streamlit
Backend: Python
AI Model: LLM (e.g., OpenAI / similar)
Processing Layer: Prompt handling & response formatting
🛠️ Tech Stack
Python
Streamlit
LLM APIs (OpenAI or similar)
GitHub for version control
🧪 Example Inputs & Outputs
Example 1

Input:

My baby has a fever, what should I do?

Output:

Monitor temperature, ensure hydration, and consult a doctor if it persists…

Example 2

Input:

Best products for newborn skincare?

Output:

Recommend gentle, fragrance-free products suitable for newborns…

⚠️ Limitations
Responses are AI-generated and may not replace professional medical advice
Limited personalization without user history
Depends on LLM accuracy
🔮 Future Improvements
🔍 Product recommendation integration
👤 User personalization
📊 Feedback loop for continuous learning
🌍 Multi-language support
🧾 RAG (Retrieval-Augmented Generation) with real Mumzworld data
📦 How to Run Locally
git clone https://github.com/Jyotiraditya3005/mumzworld-mumsupport-ai.git
cd mumzworld-mumsupport-ai
pip install -r requirements.txt
streamlit run app.py
🙌 Conclusion

MumSupport AI demonstrates how AI can:

Improve customer experience
Reduce support load
Deliver fast, scalable assistance

This project showcases a practical application of LLMs in a real-world scenario.


*Mumzworld AI-Native Intern | Track A | Jyotiraditya*
