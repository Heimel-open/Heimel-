from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
RECEIPT = ROOT / "PUBLIC_EXPORT_RECEIPT.json"
TRUST = ROOT / "attestation" / "TRUST_POLICY.json"
PUBLIC_KEY = ROOT / "attestation" / "release-public-key.pem"
SIGNATURE = ROOT / "attestation" / "release.sig"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def valid_hex64(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def canonical_hash(obj: dict) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def payload_root(entries: list[dict]) -> str:
    rows = [f"{item['path']}\0{item['sha256']}\n" for item in sorted(entries, key=lambda x: x["path"])]
    return hashlib.sha256("".join(rows).encode()).hexdigest()


def inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def run(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.run(args, input=input_bytes, capture_output=True)
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        fail(f"command failed: {' '.join(args)}: {detail}")
    return proc


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a HEIMEL public release attestation without exposing the private signing key.")
    parser.add_argument("--private-key", required=True, type=Path, help="RSA private key path outside this repository")
    parser.add_argument("--source-commitment", required=True, help="opaque 64-hex commitment produced by the private export process")
    args = parser.parse_args()

    private_key = args.private_key.expanduser().resolve()
    source_commitment = args.source_commitment.strip().lower()

    if inside_repo(private_key):
        fail("private signing key must be outside the public repository")
    if not private_key.is_file():
        fail("private signing key does not exist")
    if not valid_hex64(source_commitment):
        fail("source commitment must be exactly 64 lowercase hex characters")

    manifest = load(MANIFEST)
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        fail("release manifest has no payload")
    if manifest.get("status") not in {"PUBLIC_DRAFT", "RELEASE_CANDIDATE"}:
        fail("manifest must be PUBLIC_DRAFT or RELEASE_CANDIDATE")

    root = payload_root(entries)
    if manifest.get("root_digest") != root:
        fail("manifest root_digest does not match payload entries")

    manifest["status"] = "RELEASE_CANDIDATE"
    manifest_hash = canonical_hash(manifest)

    receipt = {
        "schema_version": 2,
        "status": "ATTESTED",
        "source_commitment": source_commitment,
        "release_manifest_sha256": manifest_hash,
        "public_payload_root_sha256": root,
        "attestation": {
            "algorithm": "RSA-SHA256",
            "public_key_path": "attestation/release-public-key.pem",
            "signature_path": "attestation/release.sig"
        }
    }

    signed = json.dumps(
        {
            "release_manifest_sha256": manifest_hash,
            "public_payload_root_sha256": root,
            "source_commitment": source_commitment,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    public_key = run("openssl", "pkey", "-in", str(private_key), "-pubout").stdout
    signature = run("openssl", "dgst", "-sha256", "-sign", str(private_key), input_bytes=signed).stdout

    trust = load(TRUST)
    trust["status"] = "CONFIGURED"

    dump(MANIFEST, manifest)
    dump(RECEIPT, receipt)
    dump(TRUST, trust)
    PUBLIC_KEY.write_bytes(public_key)
    SIGNATURE.write_bytes(signature)

    verify = run(
        "openssl", "dgst", "-sha256", "-verify", str(PUBLIC_KEY), "-signature", str(SIGNATURE),
        input_bytes=signed,
    )
    if b"Verified OK" not in verify.stdout:
        fail("signature self-check did not report Verified OK")

    print("PASS: release candidate attested")
    print(f"manifest_sha256={manifest_hash}")
    print(f"payload_root_sha256={root}")
    print(f"source_commitment={source_commitment}")
    print("PRIVATE KEY WAS NOT COPIED INTO THE REPOSITORY")


if __name__ == "__main__":
    main()
