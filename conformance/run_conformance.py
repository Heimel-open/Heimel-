from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "conformance" / "v0.2.0" / "suite.json"

def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def nested_get(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur

def needs_observation(expect: dict, result: dict) -> list[str]:
    missing = []
    if "decision" in expect or "decision_not" in expect:
        if "decision" not in result:
            missing.append("decision")
    if "effect_may_execute" in expect:
        if "effect_executed" not in result:
            missing.append("effect_executed")
    if "max_effect_count" in expect and "effect_count" not in result:
        missing.append("effect_count")
    if "fresh_authority_required" in expect and "fresh_authority_observed" not in result:
        missing.append("fresh_authority_observed")
    if "no_blind_replay" in expect and "blind_replay" not in result:
        missing.append("blind_replay")
    if expect.get("evidence_required") and "evidence" not in result:
        missing.append("evidence")
    return missing

def evaluate(test: dict, result: dict) -> tuple[str, list[str]]:
    expect = test["expect"]
    missing = needs_observation(expect, result)
    if result.get("observations_complete") is False:
        missing.append("observations_complete=false")
    if missing:
        return "INDETERMINATE", [f"missing required observation: {x}" for x in sorted(set(missing))]

    errors = []
    decision = result.get("decision")
    if decision is not None and decision not in {"ALLOW", "DENY", "ESCALATE"}:
        errors.append("invalid decision")
    if "decision" in expect and decision != expect["decision"]:
        errors.append(f"decision expected {expect['decision']} got {decision}")
    if "decision_not" in expect and decision == expect["decision_not"]:
        errors.append(f"decision must not be {expect['decision_not']}")

    executed = result.get("effect_executed")
    if executed is not None and not isinstance(executed, bool):
        errors.append("effect_executed must be boolean")
    if expect.get("effect_may_execute") is False and executed is True:
        errors.append("effect executed when testcase requires fail-closed")
    if expect.get("decision") == "ALLOW" and expect.get("effect_may_execute") is True and executed is False:
        errors.append("allowed bound effect did not execute")

    if "max_effect_count" in expect:
        count = result.get("effect_count")
        if not isinstance(count, int):
            errors.append("effect_count must be integer")
        elif count > expect["max_effect_count"]:
            errors.append(f"effect_count {count} exceeds maximum {expect['max_effect_count']}")

    if expect.get("fresh_authority_required") and result.get("fresh_authority_observed") is not True:
        errors.append("fresh authority was not observed at consequence time")
    if expect.get("no_blind_replay") and result.get("blind_replay") is not False:
        errors.append("blind replay occurred or could not be excluded")

    evidence = result.get("evidence")
    if expect.get("evidence_required") and not isinstance(evidence, dict):
        errors.append("evidence object required")
    if isinstance(evidence, dict):
        for field in expect.get("evidence_must_bind", []):
            if nested_get(evidence, field) is None:
                errors.append(f"evidence does not bind {field}")
        for field, value in expect.get("evidence_value_equals", {}).items():
            if nested_get(evidence, field) != value:
                errors.append(f"evidence {field} expected {value!r}")

    forced = expect.get("result_status")
    if forced == "FAIL" and not errors:
        errors.append("testcase declares expected conformance failure but adapter observations did not expose it")

    return ("FAIL", errors) if errors else ("PASS", [])

def invoke(command: list[str], test: dict) -> dict:
    envelope = {"protocol": "HEIMEL-CONFORMANCE/2.0", "test": test}
    proc = subprocess.run(command, input=(json.dumps(envelope, separators=(",", ":")) + "\n").encode(), capture_output=True)
    if proc.returncode != 0:
        return {"observations_complete": False, "adapter_error": proc.stderr.decode(errors="replace").strip()}
    try:
        value = json.loads(proc.stdout.decode())
    except Exception:
        return {"observations_complete": False, "adapter_error": "adapter did not return one JSON object"}
    return value if isinstance(value, dict) else {"observations_complete": False, "adapter_error": "adapter result is not object"}

def main() -> None:
    p = argparse.ArgumentParser(description="Run HEIMEL public conformance protocol 2.0.")
    p.add_argument("--adapter", required=True)
    p.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    p.add_argument("--implementation", required=True)
    p.add_argument("--configuration-digest", required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    suite_path = args.suite.resolve()
    suite = load(suite_path)
    if suite.get("schema_version") != 2 or suite.get("conformance_protocol") != "2.0":
        fail("suite must use schema_version 2 / conformance_protocol 2.0")
    tests = []
    suite_hash_rows = []
    for rel in suite.get("vector_files", []):
        vector_path = (suite_path.parent / rel).resolve()
        vector_doc = load(vector_path)
        if vector_doc.get("schema_version") != 2:
            fail(f"vector file must use schema_version 2: {rel}")
        tests.extend(vector_doc.get("tests", []))
        suite_hash_rows.append(f"{rel}\0{sha256(vector_path)}\n")
    suite_digest = hashlib.sha256(("suite.json\0" + sha256(suite_path) + "\n" + "".join(sorted(suite_hash_rows))).encode()).hexdigest()
    command = shlex.split(args.adapter)
    if not command:
        fail("adapter command is empty")

    outcomes = []
    required_ok = True
    group_status = {}
    for test in tests:
        result = invoke(command, test)
        status, errors = evaluate(test, result)
        outcomes.append({"id": test["id"], "group": test["group"], "status": status, "errors": errors})
        group_status.setdefault(test["group"], []).append(status)
        print(f"{status} {test['id']} {test['name']}")
        if test.get("required", True) and status != "PASS":
            required_ok = False

    stopgates = {}
    for group in suite.get("stopgate_groups", []):
        statuses = group_status.get(group, [])
        stopgates[group] = "PASS" if statuses and all(s == "PASS" for s in statuses) else "FAIL"
        if stopgates[group] != "PASS":
            required_ok = False

    receipt = {
        "schema_version": 2,
        "conformance_protocol": "2.0",
        "heimel_release_target": suite.get("heimel_release_target"),
        "suite_sha256": suite_digest,
        "implementation": args.implementation,
        "configuration_digest": args.configuration_digest,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "overall": "PASS" if required_ok else "FAIL",
        "stopgates": stopgates,
        "outcomes": outcomes,
    }
    if args.output:
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if required_ok else 1)

if __name__ == "__main__":
    main()
