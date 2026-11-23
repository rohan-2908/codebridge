# CodeBridge

A local verification and modernization pipeline for legacy C batch programs, built for **Code Red '26 (Track 1 — PS-01, Niveus Solutions)**.

LLMs can translate old C code into readable Python in seconds, but silent behavioral bugs—such as integer truncation, date edge cases, or permissive C string parsing—often slip through without raising compile errors. CodeBridge treats AI-generated code as an untrusted proposal: it compiles and runs the original C program as ground truth, verifies the translated Python output line-by-line, runs a bounded repair loop on failures, maps every block back to its source lines with risk flags, and requires human approval before saving the output.

## How It Works

Running `python src/main.py` executes five steps in sequence:

1. **Ground-Truth Baseline (`gcc`):** Compiles `legacy_samples/legacy_calc.c` and runs it against `legacy_samples/inputs.txt` (11 test records covering normal rows, leap years, century years, zero-day boundaries, negative values, malformed short lines, and trailing non-numeric characters).
2. **Naive One-Shot Baseline:** Sends the C file to Gemini with a plain translation prompt and checks its stdout against the C baseline to establish a fair comparison.
3. **Verified Pipeline & Repair Loop (Max 3 Attempts):** Requests a structured translation (code + line mappings + risk notes) using Pydantic schemas. Each candidate runs in a subprocess with a 10-second timeout. If stdout mismatches or a runtime error occurs, the exact failure output is fed back to Gemini for repair.
4. **Source-Line Traceability & Risk Audit:** Prints a line-range mapping (`C lines -> Python lines`) with `LOW`, `MEDIUM`, or `HIGH` risk tags and manual review notes for sensitive logic (e.g., `atoi`/`atof` parity and integer-paise truncation).
5. **Human Review Gate & Audit Log:** Keeps the generated code in a temporary file (`evaluation/.candidate_tmp.py`) and only writes to `evaluation/generated_modern.py` if the reviewer enters `A` (Accept). Every run—whether approved or rejected—is appended with timestamps, latency, token counts, and failures to `evaluation/baseline_results.json`.

## Repository Structure

```text
codebridge/
├── legacy_samples/
│   ├── legacy_calc.c           # Synthetic fixed-width C batch late-fee processor
│   └── inputs.txt              # 11 edge-case test records
├── src/
│   ├── main.py                 # Pipeline orchestration, logging, and human approval gate
│   ├── translator.py           # Gemini API client, Pydantic schemas, retries, and fallback
│   └── verifier.py             # GCC compilation, timed Python execution, and stdout diffing
├── evaluation/
│   ├── baseline_results.json   # Append-only log of all benchmark runs
│   ├── generated_modern.py     # Latest human-approved Python output
│   └── naive_modern.py         # Latest naive one-shot baseline output
├── requirements.txt
├── LICENSE
└── README.md
```

## Gemini Model Usage

* **Primary Model:** `gemini-3.6-flash` via the official `google-genai` SDK.
* **Fallback Model:** `gemini-3.5-flash-lite` (automatically triggered if the primary model hits rate limits, transient server errors, or timeouts).
* **Structured Output & Resilience:** `translator.py` enforces JSON schema output via `pydantic` (`ModernizationResult` and `LineMapping`), sets a 60-second API timeout, and uses exponential backoff retries (`2s`, `4s`) for transient HTTP `429`, `500`, `503`, and `504` errors.

## Benchmark Results

Results logged in `evaluation/baseline_results.json` across two consecutive runs on the 11-record synthetic batch dataset:

| Run | Human Gate | Naive Baseline Parity | Naive Latency / Tokens | CodeBridge Final Parity | Attempts Used | Verified Total Latency / Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Run #1 | `REJECTED` | `0/11` (0%) | 24.05s / 3,884 | `11/11` (100%) | 2 | 39.94s / 9,392 |
| Run #2 | `APPROVED` | `0/11` (0%) | 10.75s / 3,086 | `11/11` (100%) | 2 | 36.31s / 10,880 |

**Key observation:** Both the naive baseline and Attempt 1 of the verified pipeline failed identically (`ValueError: invalid literal for int() with base 10: '15X'`), because C's `atoi("15X")` silently parses the leading integer (`15`) whereas Python's `int()` raises an exception. Feeding the traceback back into Attempt 2 prompted Gemini to write explicit `c_atoi`/`c_atof` helpers, reaching `11/11` exact output parity while flagging those lines as `HIGH RISK` for human review. The trade-off is roughly 3x higher token usage and ~36–40s runtime compared to one-shot translation.

## Running Locally

### Prerequisites
* Python 3.12+
* GCC (`gcc` available in PATH; tested on Windows 11 with MinGW)
* A Google AI Studio API key (`GEMINI_API_KEY`)

### Setup & Run

```bash
git clone https://github.com/rohan-2908/codebridge.git
cd codebridge
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your_api_key_here"
python src/main.py
```

**macOS / Linux:**
```bash
export GEMINI_API_KEY="your_api_key_here"
python src/main.py
```

*(Never commit your API key. `GEMINI_API_KEY` is read strictly from environment variables.)*

## Sample Data & Licensing

* `legacy_samples/legacy_calc.c` and `legacy_samples/inputs.txt` are 100% synthetic test files written specifically for this prototype; no proprietary or customer code is included.
* Released under the **MIT License** (see `LICENSE`).

## Known Limitations

* **Single-file batch scope:** Currently targets standalone stdin/stdout C modules. Multi-file C codebases, external database calls, and pointer-heavy memory layouts are outside the current Round 1 scope.
* **Subprocess isolation only:** AI-generated Python runs locally via `subprocess` with a 10-second timeout rather than inside an isolated Docker container or sandboxed VM.
* **Test-suite coverage dependency:** Output parity only proves equivalence across the inputs provided in `inputs.txt`. Subtle IEEE-754 floating-point edge cases outside the test set still require manual engineer review.
* **Windows binary naming:** `verifier.py` currently compiles the C baseline to `evaluation/legacy_calc.exe`; macOS/Linux environments may require adjusting the executable extension.

## Scaling to Larger Codebases (Next Steps)

To move beyond a single 40-line C file to a larger open-source project (like a multi-file C or GnuCOBOL repository):
* **Splitting Large Projects:** Instead of sending an entire codebase at once, split it function-by-function or file-by-file so each small module fits cleanly into Gemini's context window and gets tested individually.
* **Safer Testing & GitHub Automation:** Run the compiled C and Python test checks inside a Docker container (instead of directly on a developer's laptop) and trigger the check automatically whenever someone opens a GitHub Pull Request.
* **Data Privacy for Real Companies:** Since free-tier AI Studio requests can be used by Google to improve models, a company using real internal code would switch the API client to Google Cloud's **Vertex AI** (which keeps private code isolated inside their own cloud region) while keeping our human `[A]ccept / [R]eject` check before merging.
