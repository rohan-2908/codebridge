import json
import textwrap
from datetime import datetime
from pathlib import Path

from translator import translate_naive, translate_verified
from verifier import compare_outputs, run_c_baseline, run_python_candidate

LEGACY_C = Path("legacy_samples/legacy_calc.c")
INPUTS = Path("legacy_samples/inputs.txt")
CANDIDATE_PY = Path("evaluation/.candidate_tmp.py")
MODERN_PY = Path("evaluation/generated_modern.py")
REPORT_JSON = Path("evaluation/baseline_results.json")


def main():
    if not LEGACY_C.exists() or LEGACY_C.stat().st_size == 0:
        print("[ERROR] Legacy source file is missing or empty.")
        return
    if not INPUTS.exists() or INPUTS.stat().st_size == 0:
        print("[ERROR] Test input file is missing or empty.")
        return

    legacy_code = LEGACY_C.read_text(encoding="utf-8")

    try:
        print("=== 1. RUNNING GROUND-TRUTH C BASELINE (GCC) ===")
        c_out = run_c_baseline(LEGACY_C, INPUTS)
        if not c_out:
            print("[ERROR] C baseline produced no output.")
            return
        print(f"Compiled & executed {len(c_out)} ground-truth records.\n")

        print("=== 2. RUNNING NAIVE ONE-SHOT BASELINE ===")
        naive_code, naive_lat, naive_tok, naive_model = translate_naive(legacy_code)
        naive_out, naive_err = run_python_candidate(
            naive_code, Path("evaluation/naive_modern.py"), INPUTS
        )
        naive_passed, naive_fails = (
            (0, [naive_err]) if naive_err else compare_outputs(c_out, naive_out)
        )
        print(
            f"Naive Parity ({naive_model}): {naive_passed}/{len(c_out)} "
            f"| Latency: {naive_lat}s | Tokens: {naive_tok}\n"
        )

        print("=== 3. RUNNING CODEBRIDGE VERIFIED PIPELINE ===")
        total_tokens, total_latency = 0, 0.0
        feedback = ""
        result = None
        attempts_log = []

        for attempt in range(1, 4):
            result, lat, tok, verified_model = translate_verified(legacy_code, feedback)
            total_latency += lat
            total_tokens += tok
            py_out, err = run_python_candidate(result.python_code, CANDIDATE_PY, INPUTS)
            passed, failures = (
                (0, [err]) if err else compare_outputs(c_out, py_out)
            )

            attempts_log.append({
                "attempt": attempt,
                "model": verified_model,
                "passed": passed,
                "total": len(c_out),
                "failures": failures,
                "latency_s": lat,
                "tokens": tok,
            })
            pct = (passed / len(c_out)) * 100
            print(
                f"[Attempt {attempt} | {verified_model}] "
                f"Output Parity: {passed}/{len(c_out)} ({pct:.0f}%)"
            )
            if not failures:
                break
            for fail in failures[:3]:
                print(f"  -> Mismatch: {fail}")
            feedback = "\n".join(failures)

        assert result is not None
        print("\n=== 4. SOURCE-LINE TRACEABILITY & RISK FLAGS ===")
        for item in result.traceability:
            print(f"[{item.risk_level} RISK] {item.legacy_lines} -> {item.modern_lines}")
            print(
                textwrap.fill(
                    item.business_rule,
                    width=76,
                    initial_indent="  Rule:  ",
                    subsequent_indent="         ",
                )
            )
            if item.risk_level != "LOW":
                print(
                    textwrap.fill(
                        item.review_note,
                        width=76,
                        initial_indent="  Check: ",
                        subsequent_indent="         ",
                    )
                )
            print()

        print("=== 5. HUMAN REVIEW GATE ===")
        decision = input(
            "Approve generated_modern.py for deployment? [A]ccept / [R]eject: "
        ).strip().upper()
        if decision == "A":
            MODERN_PY.write_text(result.python_code, encoding="utf-8")
            human_status = "APPROVED"
            print("Status: APPROVED FOR MERGE")
        else:
            human_status = "REJECTED"
            print("Status: REJECTED — FLAGGED FOR MANUAL FIX")

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_records": len(c_out),
            "human_decision": human_status,
            "naive_baseline": {
                "model": naive_model,
                "passed": naive_passed,
                "parity_pct": round((naive_passed / len(c_out)) * 100, 1),
                "latency_s": naive_lat,
                "tokens": naive_tok,
                "failures": naive_fails,
            },
            "verified_pipeline": {
                "final_passed": attempts_log[-1]["passed"],
                "parity_pct": round((attempts_log[-1]["passed"] / len(c_out)) * 100, 1),
                "total_latency_s": round(total_latency, 2),
                "total_tokens": total_tokens,
                "attempts": attempts_log,
            },
        }

        history = []
        if REPORT_JSON.exists():
            try:
                existing = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
                history = existing if isinstance(existing, list) else [existing]
            except json.JSONDecodeError:
                history = []
        history.append(report)
        REPORT_JSON.write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(f"\nSaved run #{len(history)} to {REPORT_JSON}")

    finally:
        if CANDIDATE_PY.exists():
            CANDIDATE_PY.unlink()


if __name__ == "__main__":
    main()
