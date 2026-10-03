HEIMEL PUBLIC REFERENCE ADAPTER

This directory contains a minimal public reference adapter for HEIMEL-CONFORMANCE/2.0.

Purpose
- demonstrate the public contract without private VALO dependencies
- provide an executable target for the public conformance suite
- fail closed on missing, stale, revoked, malformed or insufficient authority
- bind consequential effects to authority and evidence

Non-claim
This is a reference semantics demonstrator, not a production runtime and not evidence of independent third-party adoption.

Run
python reference/test_adapter.py
python conformance/run_conformance.py --adapter "python reference/adapter.py" --implementation "heimel-public-reference-adapter/0.2.0" --configuration-digest "dce8fdff9757e9092583d45b7d3a8f2b139532d838332fcc974e84a971e4a870"
