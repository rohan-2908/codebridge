import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class LineMapping(BaseModel):
    legacy_lines: str = Field(description="Original C line range, e.g., 'L27-L31'")
    modern_lines: str = Field(description="Translated Python line range")
    business_rule: str = Field(description="Plain-English summary of what this block does")
    risk_level: str = Field(description="'LOW', 'MEDIUM', or 'HIGH' (flag rounding, dates, or parsing)")
    review_note: str = Field(description="What an engineer should verify manually")


class ModernizationResult(BaseModel):
    python_code: str = Field(description="Complete, runnable standalone Python code reading stdin and printing stdout")
    traceability: list[LineMapping]


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")
    return genai.Client(api_key=api_key, http_options={"timeout": 60000})


def _call_with_retry(client, contents, schema=None, max_retries=3):
    config = (
        types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        )
        if schema
        else types.GenerateContentConfig()
    )

    models = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
    for model_name in models:
        for attempt in range(max_retries):
            try:
                start = time.time()
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                latency = round(time.time() - start, 2)
                tokens = getattr(resp.usage_metadata, "total_token_count", 0) or 0
                return resp, latency, tokens, model_name
            except Exception as e:
                err_str = str(e)
                is_transient = any(
                    code in err_str
                    for code in (
                        "429",
                        "503",
                        "500",
                        "504",
                        "UNAVAILABLE",
                        "RESOURCE_EXHAUSTED",
                        "DEADLINE_EXCEEDED",
                        "timeout",
                        "timed out",
                    )
                )
                if is_transient and attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"[Temporary API Load on {model_name}] Retrying in {wait}s...")
                    time.sleep(wait)
                elif is_transient or "404" in err_str:
                    print(f"[Fallback] Switching from {model_name} to next model...")
                    break
                else:
                    raise

    raise RuntimeError("All configured Gemini models failed after maximum retries.")


def translate_naive(legacy_code: str) -> tuple[str, float, int, str]:
    """Baseline: simple one-shot translation without verification rules."""
    client = get_client()
    prompt = f"Translate this C program to Python reading stdin and printing stdout. Return ONLY Python code:\n\n{legacy_code}"
    resp, latency, tokens, model_used = _call_with_retry(client, prompt, schema=None)
    fence = "`" * 3
    lines = [
        line
        for line in (resp.text or "").strip().splitlines()
        if not line.strip().startswith(fence)
    ]
    return "\n".join(lines), latency, tokens, model_used


def translate_verified(legacy_code: str, feedback: str = "") -> tuple[ModernizationResult, float, int, str]:
    """Structured translation with source-line traceability and risk flags."""
    client = get_client()
    prompt = f"""
You are an enterprise code modernization assistant. Translate the legacy C batch module into standalone Python 3.12 reading from sys.stdin and printing identical stdout.
Preserve exact fixed-width slicing, integer truncation/rounding, leap-year math, and error strings.
Provide exact source-line traceability and flag high-risk blocks for human review.

{f"PREVIOUS TEST FAILURES TO FIX:{chr(10)}{feedback}" if feedback else ""}

Legacy C Code (with line numbers):
{chr(10).join(f"{i+1}: {line}" for i, line in enumerate(legacy_code.splitlines()))}
"""
    resp, latency, tokens, model_used = _call_with_retry(client, prompt, schema=ModernizationResult)
    parsed = ModernizationResult.model_validate_json(resp.text or "{}")
    return parsed, latency, tokens, model_used
