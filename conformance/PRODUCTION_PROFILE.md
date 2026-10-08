# HEIMEL Production Conformance Profile (experimental)

The production gate is **fail-closed**. The SQLite fixtures are not an external adapter. No production PASS is available without an independently verified external observer and recovery witness.

## Required adapter capabilities

An external integration must supply `reset`, `issue_permit`, `update_authority`, `pause_at`, `commit`, `crash`, `restart`, `observe_effects`, and `export_evidence`. `observe_effects` must be backed by a separately controlled observation path; adapter responses alone are insufficient.

## Evidence contract

Provide `manifest.json`, `schedule.json`, `authority.json`, `effects.json`, `receipts.json`, `recovery.json`, `gates.json`, and `attestation.json`. Manifest includes `environment=production`, `external_adapter_id`, and SHA-256 digests of the five non-manifest evidence artifacts. `attestation.json` uses `algorithm=Ed25519`, a `key_id` provisioned out of band, and base64 signature over canonical JSON `{"manifest":...,"gates":...}`. Keys are never accepted from the bundle itself.

The current verifier checks manifest hashes and Ed25519 signatures, detects explicit gate failures, and returns INCOMPLETE for unverified external-effect/recovery witnesses. Self-declared PASS values, even signed, never establish production conformance. A separate, independently trusted witness-verification implementation and actual external adapter remain required.

## Required fault injections

Before authorization; after ALLOW but before commit; during commit; after commit before receipt; during restart; after revocation; duplicate commit; altered effect; swapped permit; altered authority version; missing observer; missing trust key; signature substitution; incomplete schedule budget.

## Verdict precedence

Verified invariant breach: FAIL. No breach but missing coverage, key, evidence or witness: INCOMPLETE. PASS only after independent witness verification and all required tests. The current implementation deliberately does not return production PASS.

## Invocation

`python3 conformance/verify_production_bundle.py /path/to/bundle --trust-store /path/to/trusted_keys.json`

Non-PASS returns a nonzero exit code. Do not store private key material in the repository.
