"""Executable experimental HEIMEL exposure vectors; separate from v0.2.0."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
from exposure import ExposureDenied, Ledger, Request  # noqa: E402


def run() -> None:
    profile = json.loads((ROOT / "conformance/exposure_profile_v0.json").read_text())
    assert profile["profile"] == "HEIMEL-EXPOSURE-EXPERIMENTAL/0.1"
    assert profile["release_status"] == "UNRELEASED"
    ids = set()
    for case in profile["cases"]:
        assert case["id"] not in ids
        ids.add(case["id"])
        with tempfile.TemporaryDirectory() as tmp:
            store = Ledger(Path(tmp) / "accounting.db")
            for step in case["steps"]:
                if "transition" in step:
                    store.transition(step.get("tenant", "tenant"), step["id"], step["transition"])
                    continue
                request = replace(Request(
                    tenant="tenant", scope="budget", dimension="money", unit="minor:NOK",
                    request_id=step["id"], amount=step["amount"], ceiling=100,
                    now=1000, window=60,
                ), **{k: v for k, v in step.items() if k in ("tenant", "scope", "unit", "now", "window")})
                try:
                    actual = store.reserve(request)
                except ExposureDenied:
                    actual = "DENY"
                assert actual == step["expect"], (case["id"], step, actual)
        print("PASS", case["id"], case["name"])
    print(f"PASS: {len(ids)} experimental exposure vectors")


if __name__ == "__main__":
    run()
