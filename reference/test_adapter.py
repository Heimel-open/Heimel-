from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "reference" / "adapter.py"


def call(test: dict) -> dict:
    envelope = {"protocol": "HEIMEL-CONFORMANCE/2.0", "test": test}
    proc = subprocess.run([sys.executable, str(ADAPTER)], input=(json.dumps(envelope)+"\n").encode(), capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.decode())
    return json.loads(proc.stdout.decode())


def base_test() -> dict:
    return {
        "id": "REF-001",
        "group": "freshness",
        "name": "reference-allows-valid-bound-effect",
        "required": True,
        "mode": "single",
        "input": {
            "authority": {
                "present": True,
                "revoked": False,
                "valid_from": "2026-10-02T12:00:00Z",
                "expires_at": "2026-10-02T13:00:00Z",
                "checked_at": "2026-10-02T12:30:00Z",
                "scope": ["lamp-1:on"],
                "version": "A2",
                "actor": "actor-1",
                "tenant": "tenant-1",
                "delegation_chain_valid": True
            },
            "effect": {
                "id": "lamp-1",
                "action": "on",
                "parameters": {"level": 1},
                "authority_version": "A2",
                "actor": "actor-1",
                "tenant": "tenant-1"
            },
            "required_info_complete": True
        },
        "expect": {"decision": "ALLOW", "effect_may_execute": True, "evidence_required": True}
    }


def main() -> None:
    valid = base_test()
    result = call(valid)
    assert result["decision"] == "ALLOW"
    assert result["effect_executed"] is True
    assert result["fresh_authority_observed"] is True
    assert result["evidence"]["authority_version"] == "A2"

    revoked = base_test()
    revoked["id"] = "REF-002"
    revoked["input"]["authority"]["revoked"] = True
    result = call(revoked)
    assert result["decision"] != "ALLOW"
    assert result["effect_executed"] is False

    stale = base_test()
    stale["id"] = "REF-003"
    stale["input"]["effect"]["authority_version"] = "A1"
    result = call(stale)
    assert result["decision"] != "ALLOW"
    assert result["effect_executed"] is False

    print("PASS: reference adapter unit tests")


if __name__ == "__main__":
    main()
