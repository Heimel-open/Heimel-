"""Fail-closed content verification for the separate, UNSIGNED exposure RC.

This is not a signature verifier and cannot promote an unsigned candidate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "release/v0.3.0-rc1/manifest.json"
APPROVED = frozenset({
    "reference/exposure.py", "reference/test_exposure.py", "reference/EXPOSURE_SCOPE.txt",
    "conformance/exposure_profile_v0.json", "conformance/test_exposure_profile.py",
})


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: exposure candidate integrity: {reason}")


def verify() -> None:
    m = json.loads(CANDIDATE.read_text())
    require(m.get("version") == "0.3.0-rc1", "version")
    require(m.get("base_release") == "v0.2.0", "base version")
    require(m.get("status") == "UNSIGNED_RELEASE_CANDIDATE", "status")
    require(m.get("signature") is None and m.get("source_commitment") is None, "unsigned provenance")
    require(m.get("release_manifest_sha256") is None, "unsigned manifest")
    files = m.get("files")
    require(isinstance(files, list), "file list")
    paths = [entry.get("path") for entry in files if isinstance(entry, dict)]
    require(paths == sorted(APPROVED) and len(paths) == len(files), "exact allowlist")
    for f in files:
        require(hashlib.sha256((ROOT / f["path"]).read_bytes()).hexdigest() == f.get("sha256"), "file hash " + f["path"])
    rows = "".join(f"{f['path']}\0{f['sha256']}\n" for f in files).encode()
    require(hashlib.sha256(rows).hexdigest() == m.get("root_digest"), "payload root")
    q = m.get("qualification") or {}
    require(q.get("independent_review") == "NOT_COMPLETED", "independent review")
    require(q.get("production_effect") == "NOT_VERIFIED", "production qualification")
    print("PASS: v0.3.0-rc1 candidate integrity; UNSIGNED, not released")


if __name__ == "__main__":
    verify()
