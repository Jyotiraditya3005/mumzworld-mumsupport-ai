"""
evals.py — Evaluation harness for MumzSupport AI
Runs all test cases, scores them, outputs a report.

Usage:
    python evals.py --api-key YOUR_KEY
    python evals.py --api-key YOUR_KEY --model meta-llama/llama-3.3-70b-instruct:free
    python evals.py --api-key YOUR_KEY --output evals/results.json
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))
from src.classifier import classify_email


# ─── Scoring Logic ──────────────────────────────────────────────────────────────

def score_result(test_case: dict, response) -> dict:
    """
    Returns a scored result dict for one test case.
    
    Intent score:   1.0 if exact match, 0.5 if both unknown/ambiguous, 0.0 otherwise
    Urgency score:  1.0 if exact match, 0.5 if off by one level, 0.0 if way off
    Safety check:   1.0 if TC-006, TC-015, TC-018 have needs_escalation=True
    Uncertainty:    1.0 if adversarial inputs return confidence < 0.6
    """
    tc_id = test_case["id"]
    expected_intent = test_case["expected_intent"]
    expected_urgency = test_case["expected_urgency"]

    intent_score = 1.0 if response.intent == expected_intent else (
        0.5 if (response.intent == "unknown" and expected_intent in ["unknown"]) else 0.0
    )

    urgency_levels = {"low": 0, "medium": 1, "high": 2, "unknown": -1}
    exp_u = urgency_levels.get(expected_urgency, -1)
    got_u = urgency_levels.get(response.urgency, -1)

    if exp_u == -1 or got_u == -1:
        urgency_score = 1.0 if expected_urgency == response.urgency else 0.5
    else:
        diff = abs(exp_u - got_u)
        urgency_score = 1.0 if diff == 0 else (0.5 if diff == 1 else 0.0)

    # Safety escalation check
    safety_pass = True
    if tc_id in ["TC-006", "TC-015", "TC-018"]:
        if not response.needs_escalation:
            safety_pass = False

    # Uncertainty handling check (adversarial cases)
    uncertainty_pass = True
    if test_case["label"] == "adversarial" and expected_intent == "unknown":
        if response.confidence > 0.7:
            uncertainty_pass = False

    # Arabic present
    arabic_present = bool(response.reply_ar and len(response.reply_ar.strip()) > 10)

    # Composite score
    composite = (intent_score * 0.45) + (urgency_score * 0.25) + (
        (1.0 if safety_pass else 0.0) * 0.15
    ) + (
        (1.0 if uncertainty_pass else 0.0) * 0.15
    )

    return {
        "id": tc_id,
        "label": test_case["label"],
        "expected_intent": expected_intent,
        "got_intent": response.intent,
        "expected_urgency": expected_urgency,
        "got_urgency": response.urgency,
        "confidence": response.confidence,
        "intent_score": intent_score,
        "urgency_score": urgency_score,
        "safety_pass": safety_pass,
        "uncertainty_pass": uncertainty_pass,
        "arabic_present": arabic_present,
        "needs_escalation": response.needs_escalation,
        "composite_score": round(composite, 3),
        "passed": composite >= 0.6,
        "notes": test_case["notes"]
    }


# ─── Main Runner ────────────────────────────────────────────────────────────────

def run_evals(api_key: str, model: str, output_path: str = None):
    data_path = Path(__file__).parent / "data" / "test_emails.json"
    test_cases = json.loads(data_path.read_text())

    print(f"\n{'='*60}")
    print(f"  MumzSupport AI — Evaluation Suite")
    print(f"  Model: {model}")
    print(f"  Test cases: {len(test_cases)}")
    print(f"{'='*60}\n")

    results = []
    passed = 0
    failed = 0

    for i, tc in enumerate(test_cases):
        print(f"  [{i+1:02d}/{len(test_cases)}] {tc['id']} ({tc['label']})... ", end="", flush=True)
        
        try:
            response = classify_email(tc["email"], api_key, model)
            scored = score_result(tc, response)
            scored["reply_en_preview"] = response.reply_en[:100] + "..." if len(response.reply_en) > 100 else response.reply_en
            scored["reply_ar_preview"] = response.reply_ar[:80] + "..." if len(response.reply_ar) > 80 else response.reply_ar
            scored["reasoning"] = response.reasoning
            scored["uncertainty_note"] = response.uncertainty_note
            results.append(scored)

            status = "✅ PASS" if scored["passed"] else "❌ FAIL"
            print(f"{status}  (intent: {scored['got_intent']}, urgency: {scored['got_urgency']}, conf: {scored['confidence']:.2f}, score: {scored['composite_score']:.2f})")

            if scored["passed"]:
                passed += 1
            else:
                failed += 1
                print(f"       └─ Expected: intent={scored['expected_intent']}, urgency={scored['expected_urgency']}")
                if not scored["safety_pass"]:
                    print(f"       └─ ⚠️  SAFETY FAIL: should have triggered escalation")

            # Small delay to respect rate limits
            time.sleep(1.5)

        except Exception as e:
            print(f"💥 ERROR: {e}")
            results.append({
                "id": tc["id"],
                "label": tc["label"],
                "error": str(e),
                "passed": False,
                "composite_score": 0.0
            })
            failed += 1

    # ─── Summary ─────────────────────────────────────────────────────────────

    total = len(results)
    pass_rate = passed / total * 100
    avg_score = sum(r.get("composite_score", 0) for r in results) / total
    avg_confidence = sum(r.get("confidence", 0) for r in results) / total

    # By label
    for label in ["easy", "medium", "adversarial"]:
        subset = [r for r in results if r.get("label") == label]
        if subset:
            subset_pass = sum(1 for r in subset if r.get("passed", False))
            print(f"\n  {label.upper():12s}: {subset_pass}/{len(subset)} passed")

    print(f"\n{'='*60}")
    print(f"  OVERALL: {passed}/{total} passed ({pass_rate:.1f}%)")
    print(f"  Avg composite score:  {avg_score:.3f}")
    print(f"  Avg model confidence: {avg_confidence:.3f}")

    # Safety check summary
    safety_cases = [r for r in results if r.get("id") in ["TC-006", "TC-015", "TC-018"]]
    safety_passed = sum(1 for r in safety_cases if r.get("safety_pass", False))
    print(f"  Safety escalation:    {safety_passed}/{len(safety_cases)} critical cases escalated correctly")
    print(f"{'='*60}\n")

    # ─── Output ───────────────────────────────────────────────────────────────

    summary = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "model": model,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate_pct": round(pass_rate, 1),
        "avg_composite_score": round(avg_score, 3),
        "avg_confidence": round(avg_confidence, 3),
        "safety_escalation_rate": f"{safety_passed}/{len(safety_cases)}",
        "results": results
    }

    out = output_path or "evals/results.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"  Results saved to: {out}\n")

    return summary


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MumzSupport AI Eval Runner")
    parser.add_argument("--api-key", required=True, help="OpenRouter API key")
    parser.add_argument("--model", default="meta-llama/llama-3.3-70b-instruct:free", help="Model ID")
    parser.add_argument("--output", default="evals/results.json", help="Output path for results JSON")
    args = parser.parse_args()

    run_evals(args.api_key, args.model, args.output)
