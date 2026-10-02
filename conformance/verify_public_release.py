from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
RECEIPT = ROOT / "PUBLIC_EXPORT_RECEIPT.json"
BOUNDARY = ROOT / "PUBLIC_BOUNDARY.json"
TRUST = ROOT / "attestation" / "TRUST_POLICY.json"

EVIDENCE_FILES = {
    "RELEASE_MANIFEST.json",
    "PUBLIC_EXPORT_RECEIPT.json",
    "attestation/TRUST_POLICY.json",
}

INFRA_PREFIXES = (".github/", "conformance/", "schemas/", "release/", "attestation/")
ROOT_INFRA = {"VERSION", "START_HERE.txt", "PUBLIC_BOUNDARY.json"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tracked_files() -> set[str]:
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return {p.decode() for p in out.split(b"\0") if p}


def canonical_manifest_hash(manifest: dict) -> str:
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def payload_root(entries: list[dict]) -> str:
    rows = [f"{item['path']}\0{item['sha256']}\n" for item in sorted(entries, key=lambda x: x["path"])]
    return hashlib.sha256("".join(rows).encode()).hexdigest()


def main() -> None:
    manifest = load(MANIFEST)
    receipt = load(RECEIPT)
    boundary = load(BOUNDARY)
    trust = load(TRUST)
    tracked = tracked_files()

    if boundary.get("mode") != "fail_closed":
        fail("PUBLIC_BOUNDARY must be fail_closed")

    entries = manifest.get("files")
    if not isinstance(entries, list):
        fail("manifest files must be a list")

    listed: set[str] = set()
    for item in entries:
        path = item.get("path")
        digest = item.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            fail("each manifest entry requires path and sha256")
        if path in listed:
            fail(f"duplicate manifest path: {path}")
        if path in EVIDENCE_FILES or path in ROOT_INFRA or path.startswith(INFRA_PREFIXES):
            fail(f"infrastructure/evidence cannot be release payload: {path}")
        target = ROOT / path
        if not target.is_file():
            fail(f"manifest path missing: {path}")
        actual = sha256(target)
        if actual != digest:
            fail(f"hash mismatch: {path}")
        listed.add(path)

    allowed_non_payload = set(EVIDENCE_FILES) | set(ROOT_INFRA)
    for path in tracked:
        if path in listed or path in allowed_non_payload or path.startswith(INFRA_PREFIXES):
            continue
        fail(f"tracked file is neither payload nor verification infrastructure: {path}")

    root = payload_root(entries)
    expected_root = manifest.get("root_digest")
    if expected_root not in (None, root):
        fail("manifest root_digest mismatch")

    status = manifest.get("status")
    if status == "SCRATCH_NOT_RELEASED":
        if receipt.get("status") != "NOT_ATTESTED":
            fail("scratch manifest requires NOT_ATTESTED receipt")
        print("PASS: structural public verification; repository is not release-ready")
        return

    if status != "RELEASE_CANDIDATE":
        fail(f"unknown manifest status: {status}")

    if receipt.get("status") != "ATTESTED":
        fail("release candidate requires ATTESTED receipt")
    if trust.get("status") != "CONFIGURED":
        fail("release candidate requires configured public trust policy")
    if receipt.get("release_manifest_sha256") != canonical_manifest_hash(manifest):
        fail("receipt does not bind canonical release manifest")
    if receipt.get("public_payload_root_sha256") != root:
        fail("receipt does not bind public payload root")
    source = receipt.get("source_commitment")
    if not isinstance(source, str) or len(source) != 64:
        fail("receipt requires opaque 64-hex source_commitment")

    signature_file = ROOT / "attestation" / "release.sig"
    public_key = ROOT / "attestation" / "release-public-key.pem"
    if not signature_file.is_file() or not public_key.is_file():
        fail("attestation signature/public key missing")

    signed_payload = json.dumps(
        {
            "release_manifest_sha256": receipt["release_manifest_sha256"],
            "public_payload_root_sha256": receipt["public_payload_root_sha256"],
            "source_commitment": receipt["source_commitment"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    temp = ROOT / ".attestation-payload.tmp"
    temp.write_bytes(signed_payload)
    try:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(public_key), "-signature", str(signature_file), str(temp)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            fail("release attestation signature invalid")
    finally:
        temp.unlink(missing_ok=True)

    print("PASS: release manifest, payload root, source commitment and signature verified")


if __name__ == "__main__":
    main()
