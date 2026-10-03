# HEIMEL

HEIMEL is a public, verifiable authority-to-consequence contract for consequence-bearing AI and software actions.

It answers a narrow question at the point where intent becomes real-world effect:

> Is this exact consequence authorized now, under current authority and conditions, and can the decision and observed effect be verified afterwards?

## Current public release

**HEIMEL v0.2.0** — immutable public release

- Release: https://github.com/Heimel-open/Heimel-/releases/tag/v0.2.0
- Commit: `456e16935ac2cf0b4f47bc1343b5663cad240dea`
- Conformance protocol: `HEIMEL-CONFORMANCE/2.0`
- Normative vectors: **79 REQUIRED**
- Reference result: **79/79 PASS**
- Formal models: `ConsequenceBoundary` and `AuthorityConfinement`

## What is public

The public HEIMEL core defines and tests:

- fresh authority at consequence time;
- exact effect binding;
- fail-closed handling of missing or unknown required information;
- one-shot / replay protection;
- no direct effect path;
- actor, tenant and delegation confinement;
- concurrency and recovery edge cases;
- evidence binding and replayable receipts;
- executable conformance testing;
- a minimal public reference adapter;
- signed release manifests and public verification.

## What HEIMEL is not

HEIMEL is not the full VALO stack and it is not the full private REHT implementation.

The public project exposes the normative consequence-time authority contract and the conformance surface required to test implementations against it. It does **not** publish VALO's broader runtime, orchestration, authority-resolution internals, product packs, workflow machinery, private research, or product-specific implementation logic.

A useful boundary is:

`public HEIMEL = contract + formal model + conformance + evidence`

`VALO / REHT = broader implementation, resolution, runtime and product systems`

## Verify

Start with:

- `START_HERE.txt`
- `PUBLIC_BOUNDARY.json`
- `RELEASE_MANIFEST.json`
- `PUBLIC_EXPORT_RECEIPT.json`
- `conformance/CONTRACT.txt`
- `conformance/v0.2.0/`
- `reference/adapter.py`
- `spec/formal/`

The release verifier is:

```bash
python conformance/verify_public_release.py
```

The public reference adapter can be checked against the v0.2.0 suite with:

```bash
python conformance/run_conformance.py \
  --adapter "python reference/adapter.py" \
  --implementation "heimel-public-reference-adapter/0.2.0" \
  --configuration-digest "dce8fdff9757e9092583d45b7d3a8f2b139532d838332fcc974e84a971e4a870"
```

## Public site

https://heimel.xyz/

## License and release boundary

Use the repository's declared licensing and release metadata for authoritative terms. A GitHub branch may continue to evolve after a release; the immutable release tag is the stable historical reference.
