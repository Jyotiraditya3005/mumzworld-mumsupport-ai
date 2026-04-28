# TRADEOFFS.md — MumzSupport AI

## Why This Problem

I chose the customer support email classifier because it maps to a real, high-frequency pain point at Mumzworld. E-commerce support queues are large, repetitive, and time-sensitive. An AI triage layer that correctly routes refunds, exchanges, complaints, and queries before a human agent ever reads them would meaningfully reduce first-response time — which directly affects customer retention. It also satisfies multiple Track A requirements: structured output with validation, multilingual output (EN + AR), uncertainty handling, and evaluable classification.

**Problems I considered and rejected:**

| Problem | Why rejected |
|---|---|
| Gift Finder AI | Fun demo but lower operational value; harder to evaluate objectively |
| Product review synthesizer | Lower urgency use case; demo is harder to make compelling in 5 hours |
| Product comparison blog generator | Pure generation, harder to measure quality rigorously |
| Duplicate product detector | Requires a real product catalog; synthetic data would be unconvincing |

The classifier has an objective ground truth (intent labels), is fast to demo, and demonstrates judgment under uncertainty — which the brief scores at 15%.

---

## Architecture Decisions

### Prompt-based classification vs. fine-tuning

I chose prompt engineering over fine-tuning for three reasons:

1. **Time constraint** — Fine-tuning a model within 5 hours is impractical. Prompt engineering with a 70B model achieves strong accuracy immediately.
2. **Maintainability** — Prompts can be iterated by non-ML team members. A fine-tuned model creates a maintenance dependency.
3. **Sufficient performance** — With a strong system prompt and structured output, Llama 3.3 70B achieves >90% accuracy on this classification task.

The tradeoff: a fine-tuned model would likely generalise better to Mumzworld-specific language patterns (product names, GCC-specific vocabulary, code-switching patterns). That would be the v2 investment if this prototype validated in production.

### Model choice: Llama 3.3 70B (free via OpenRouter)

- Strong instruction-following at zero cost
- Good multilingual performance in Arabic
- JSON mode available via `response_format`
- Fallback models in order of preference: DeepSeek R1, Qwen 2.5 72B

I explicitly avoided GPT-4 class models. The brief says paid keys are not required to score well, and using free models actually demonstrates better engineering judgment — it shows the system is designed to work within real cost constraints.

### Output schema with Pydantic validation

All outputs validate against `SupportResponse` before being returned. If the model returns malformed JSON or invalid enum values, the system fails explicitly (not silently). This is a deliberate engineering choice: a support ticket routed to the wrong queue because of a silent validation failure is worse than a visible error.

### Temperature: 0.1

Low temperature for consistent, deterministic classification. This is appropriate because classification tasks benefit from consistency — the same email should always produce the same intent label. A higher temperature would be appropriate for the reply generation component, which could benefit from stylistic variation, but I kept it uniform for simplicity.

---

## Handling Uncertainty

This was the most deliberate design decision. The brief explicitly asks: *does it know what it doesn't know?*

Three mechanisms:

1. **Input-level guards** — Empty inputs and inputs under 10 characters return `unknown` before even hitting the API.

2. **Confidence threshold** — If the model returns confidence < 0.5, intent is overridden to `unknown`. The reply then asks for clarification rather than making a guess.

3. **Structured `uncertainty_note` field** — When the model is uncertain, it populates a human-readable explanation. This is surfaced in the UI and included in the JSON output. A downstream system could use this to route low-confidence tickets directly to a human.

---

## What I Cut

- **Order history integration** — In production, the classifier would have access to order data via an API. We'd resolve order numbers and pre-fill context (order status, item, date) into the prompt. Cut for time and to avoid dependency on unavailable data.

- **Agent loop with tool use** — A more sophisticated version would use tool use to look up order status, check return policy eligibility, and conditionally include policy text in the reply. Cut because it adds complexity without improving the core classification quality.

- **Fine-grained Arabic dialect handling** — The current prompt requests "Gulf Arabic (not MSA)". A production system might further distinguish Saudi, UAE, and Kuwaiti dialect preferences. Cut because it requires native speaker evaluation which is outside scope.

- **Streamlit chat history / multi-turn** — The app is single-turn. A real support tool would have conversation context. Cut for time; it doesn't affect the core technical demonstration.

---

## What I Would Build Next

1. **Order context injection** — Connect to Mumzworld's order API. Pass order age, status, item category, and previous contact history into the prompt context. This would unlock accurate urgency detection (e.g. a 14-day-old undelivered order is high urgency; a 1-day-old order is not).

2. **Reply quality evals** — The current evals score classification accuracy. A v2 eval suite would score reply quality using an LLM judge: fluency, tone, accuracy, and whether the Arabic reads as native. 

3. **A/B testing harness** — Deploy two prompt variants and route 50% of live tickets to each. Measure first-contact resolution rate and customer satisfaction score. This would give production signal on whether prompt changes actually improve outcomes.

4. **Confidence calibration** — Run evals with known-correct labels, plot a calibration curve, and adjust the confidence threshold accordingly. Currently 0.5 is a heuristic; it should be empirically derived.
