import subprocess
import sys
from pathlib import Path


def run_c_baseline(c_file: Path, input_file: Path) -> list[str]:
    exe_path = Path("evaluation/legacy_calc.exe")
    exe_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gcc", str(c_file), "-o", str(exe_path)], check=True)
    with open(input_file, "r", encoding="utf-8") as inp:
        res = subprocess.run(
            [str(exe_path)],
            stdin=inp,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    return res.stdout.strip().splitlines()


def run_python_candidate(
    py_code: str, out_file: Path, input_file: Path
) -> tuple[list[str], str]:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(py_code, encoding="utf-8")
    try:
        with open(input_file, "r", encoding="utf-8") as inp:
            res = subprocess.run(
                [sys.executable, str(out_file)],
                stdin=inp,
                capture_output=True,
                text=True,
                timeout=10,
            )
    except subprocess.TimeoutExpired:
        return [], "Execution timed out after 10s (possible infinite loop)."

    if res.returncode != 0:
        return [], res.stderr.strip()
    return res.stdout.strip().splitlines(), ""


def compare_outputs(expected: list[str], actual: list[str]) -> tuple[int, list[str]]:
    failures = []
    passed = 0
    total = max(len(expected), len(actual))
    for i in range(total):
        exp = expected[i] if i < len(expected) else "<EOF>"
        act = actual[i] if i < len(actual) else "<EOF>"
        if exp == act:
            passed += 1
        else:
            failures.append(f"Record {i+1}: Expected '{exp}' | Got '{act}'")
    return passed, failures
