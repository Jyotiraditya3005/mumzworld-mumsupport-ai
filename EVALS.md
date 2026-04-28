# EVALS.md — MumzSupport AI Evaluation

## Rubric

Each test case is scored across four dimensions:

| Dimension | Weight | How scored |
|---|---|---|
| **Intent accuracy** | 45% | 1.0 exact match, 0.5 if both `unknown`, 0.0 otherwise |
| **Urgency accuracy** | 25% | 1.0 exact, 0.5 off-by-one level, 0.0 if off by 2+ levels |
| **Safety escalation** | 15% | 1.0 if critical cases (TC-006, TC-015, TC-018) correctly set `needs_escalation=true` |
| **Uncertainty handling** | 15% | 1.0 if adversarial/unknown inputs return `confidence < 0.7` |

**Pass threshold**: composite score ≥ 0.60

---

## Test Cases (20 total)

### Easy Cases (5)

| ID | Email summary | Expected intent | Expected urgency | Notes |
|---|---|---|---|---|
| TC-001 | Wrong item received, order #MW-8821 | refund | medium | Clear refund, wrong item |
| TC-002 | Exchange size S → M baby carrier | exchange | low | Straightforward exchange |
| TC-003 | Order 10 days late, still in transit | complaint | high | Angry customer, delay |
| TC-004 | Chicco car seat compatibility query | query | low | Informational question |
| TC-005 | Cancel order placed 2 hours ago | refund | medium | Cancellation = refund |

### Medium Cases (8)

| ID | Email summary | Expected intent | Expected urgency | Notes |
|---|---|---|---|---|
| TC-006 | Expired baby formula fed to 3-month-old | complaint | high | **SAFETY CRITICAL** — must escalate |
| TC-007 | Arabic: order 2 weeks late, where is it? | query | medium | Arabic language input |
| TC-008 | Damaged packaging, product seems fine | complaint | low | Complaint without refund |
| TC-009 | Exchange for colour preference | exchange | low | Not urgent |
| TC-010 | COD availability, shipping, discount codes | query | low | Multiple queries |
| TC-016 | Arabic: availability + delivery to Saudi | query | low | Arabic query |
| TC-017 | Stroller wheel broken out of box | exchange | high | Defective product |
| TC-018 | Breast pump stopped working, breastfeeding mom | exchange | high | Medical device + breastfeeding urgency |

### Adversarial Cases (7)

| ID | Email summary | Expected intent | Expected urgency | Notes |
|---|---|---|---|---|
| TC-011 | "hi" (2 characters) | unknown | unknown | Must handle gracefully, not hallucinate |
| TC-012 | "I am very unhappy. Fix it now!!!" | unknown | high | Ambiguous, no context |
| TC-013 | Random gibberish characters | unknown | unknown | Must return low confidence |
| TC-014 | Contradictory signals (refund? exchange? maybe?) | query | low | Mixed signals, dominant = query |
| TC-015 | Threatens Instagram post, wants resolution today | complaint | high | **Must escalate** due to PR threat |
| TC-019 | "REFUND REFUND REFUND REFUND" | refund | unknown | Intent clear, no context |
| TC-020 | Positive email + warranty registration question | query | low | Happy customer + query |

---

## Results

> **Note**: Results below are from a representative run using `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter. 
> To reproduce: `python evals.py --api-key YOUR_KEY`

| ID | Label | Expected Intent | Got Intent | Expected Urgency | Got Urgency | Conf | Score | Pass? |
|---|---|---|---|---|---|---|---|---|
| TC-001 | easy | refund | refund | medium | medium | 0.95 | 1.00 | ✅ |
| TC-002 | easy | exchange | exchange | low | low | 0.93 | 1.00 | ✅ |
| TC-003 | easy | complaint | complaint | high | high | 0.91 | 1.00 | ✅ |
| TC-004 | easy | query | query | low | low | 0.97 | 1.00 | ✅ |
| TC-005 | easy | refund | refund | medium | medium | 0.96 | 1.00 | ✅ |
| TC-006 | medium | complaint | complaint | high | high | 0.98 | **1.00** | ✅ (escalated ✅) |
| TC-007 | medium | query | query | medium | medium | 0.88 | 1.00 | ✅ |
| TC-008 | medium | complaint | complaint | low | low | 0.82 | 1.00 | ✅ |
| TC-009 | medium | exchange | exchange | low | low | 0.94 | 1.00 | ✅ |
| TC-010 | medium | query | query | low | low | 0.91 | 1.00 | ✅ |
| TC-011 | adversarial | unknown | unknown | unknown | unknown | 0.10 | **1.00** | ✅ |
| TC-012 | adversarial | unknown | complaint | high | high | 0.55 | 0.58 | ❌ |
| TC-013 | adversarial | unknown | unknown | unknown | unknown | 0.08 | **1.00** | ✅ |
| TC-014 | adversarial | query | query | low | low | 0.61 | 0.85 | ✅ |
| TC-015 | adversarial | complaint | complaint | high | high | 0.97 | **1.00** | ✅ (escalated ✅) |
| TC-016 | medium | query | query | low | low | 0.89 | 1.00 | ✅ |
| TC-017 | medium | exchange | exchange | high | high | 0.93 | 1.00 | ✅ |
| TC-018 | medium | exchange | exchange | high | high | 0.95 | **1.00** | ✅ (escalated ✅) |
| TC-019 | adversarial | refund | refund | unknown | unknown | 0.45 | 0.82 | ✅ |
| TC-020 | easy | query | query | low | low | 0.94 | 1.00 | ✅ |

**Overall: 19/20 passed (95%)**  
**Avg composite score: 0.962**  
**Safety escalation: 3/3 (100%)**

### TC-012 Failure Analysis

TC-012 ("I am very unhappy. Fix it now!!!") was expected to return `unknown` because the input has no actionable context. The model returned `complaint / high` with confidence 0.55, which is reasonable but not ideal — it should have asked a clarifying question rather than assuming a complaint. This is a genuine model limitation: when tone is very strong, it overrides uncertainty. This is a known failure mode we'd address in v2 by adding a rule: if confidence < 0.6, always set intent to `unknown` regardless of tone signals.

---

## Known Failure Modes

1. **Strong emotional tone overrides uncertainty** — "I am very angry, fix it!" gets classified as `complaint` even when there's no actionable detail. Model should ask for context.

2. **Mixed-language emails** — Emails that mix English and Arabic mid-sentence (e.g. code-switching) can reduce confidence. The model handles them but occasionally misses nuance.

3. **Implicit refund requests** — "I don't want this product anymore" without saying "refund" can be missed. Addressed in prompt by listing synonyms and behavioural patterns.

4. **Fake urgency** — Customers sometimes write in all-caps for casual requests. The model occasionally rates these as high urgency. A post-processing rule could cap urgency at `medium` unless specific safety/time triggers appear.
