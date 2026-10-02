from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "conformance" / "v0.1.0" / "test-vectors.json"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def nested_get(obj: dict, dotted: str):
    current = obj
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def evaluate(test: dict, result: dict) -> list[str]:
    errors: list[str] = []
    expect = test["expect"]
    decision = result.get("decision")
    if decision not in {"ALLOW", "DENY", "ESCALATE"}:
        errors.append("invalid decision")
    if "decision" in expect and decision != expect["decision"]:
        errors.append(f"decision expected {expect['decision']} got {decision}")
    if "decision_not" in expect and decision == expect["decision_not"]:
        errors.append(f"decision must not be {expect['decision_not']}")

    executed = result.get("effect_executed")
    if not isinstance(executed, bool):
        errors.append("effect_executed must be boolean")
    elif expect.get("effect_may_execute") is False and executed:
        errors.append("effect executed when testcase requires fail-closed")
    elif expect.get("decision") == "ALLOW" and expect.get("effect_may_execute") is True and not executed:
        errors.append("allowed bound effect did not execute")

    evidence = result.get("evidence")
    if expect.get("evidence_required") and not isinstance(evidence, dict):
        errors.append("evidence object required")
    if isinstance(evidence, dict):
        for field in expect.get("evidence_must_bind", []):
            if nested_get(evidence, field) is None:
                errors.append(f"evidence does not bind {field}")

    return errors


def invoke(command: list[str], payload: dict) -> dict:
    proc = subprocess.run(
        command,
        input=(json.dumps(payload, separators=(",", ":")) + "\n").encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace").strip()
        fail(f"adapter exited {proc.returncode}: {stderr}")
    try:
        return json.loads(proc.stdout.decode())
    except Exception as exc:
        fail(f"adapter did not return one JSON result object: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the public HEIMEL conformance suite against an implementation adapter.")
    parser.add_argument("--adapter", required=True, help="command that reads one JSON testcase input from stdin and writes one JSON result to stdout")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--implementation", required=True, help="implementation name and version")
    parser.add_argument("--configuration-digest", required=True, help="opaque digest identifying the tested configuration")
    parser.add_argument("--output", type=Path, help="optional JSON conformance receipt path")
    args = parser.parse_args()

    suite_path = args.suite.resolve()
    suite = load(suite_path)
    command = shlex.split(args.adapter)
    if not command:
        fail("adapter command is empty")

    outcomes = []
    passed = True
    for test in suite.get("tests", []):
        result = invoke(command, test["input"])
        errors = evaluate(test, result)
        ok = not errors
        if test.get("required", True) and not ok:
            passed = False
        outcomes.append({"id": test["id"], "pass": ok, "errors": errors})
        print(f"{'PASS' if ok else 'FAIL'} {test['id']} {test['name']}")

    receipt = {
        "schema_version": 1,
        "heimel_release": suite.get("heimel_release"),
        "suite_sha256": sha256(suite_path),
        "implementation": args.implementation,
        "configuration_digest": args.configuration_digest,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "overall": "PASS" if passed else "FAIL",
        "outcomes": outcomes,
    }

    if args.output:
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
