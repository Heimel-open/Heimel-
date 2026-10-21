# Authority semantics and enforceable Handlingsrett

Status: public architecture clarification / proposal (2026-10-21). Not a change to the frozen HEIMEL Open / Enterprise / VALO boundary of 2026-10-08.

## Thesis

**Authority is not merely something a system understands. It is something the system must be unable to exceed.**

Semantic instruments may classify, represent, interpret, and explain authority claims. That is valuable evidence, but it does not by itself establish current legitimate authority to cause an exact real-world effect or prevent an unauthorized effect.

HEIMEL addresses **Handlingsrett at the consequence boundary**, independent of actor and executor type.

## Boundary contract

1. An actor (human, agent, organization, workflow, API, or robot) proposes an effect.
2. Evidence, including semantic authority descriptions, may be supplied by independent sources.
3. A trusted authority mechanism resolves fresh mandate, delegation, scope, constraints, and revocation at consequence time.
4. An effect-bound authorization permits only the stated consequential action in the stated context.
5. The governed execution path independently enforces ALLOW, DENY, or ESCALATE and fails closed on invalid, absent, or revoked authority.
6. A verifiable receipt binds authority, decision, attempted effect, and observed outcome.

## Non-exclusivity

HEIMEL does not claim exclusive ownership of the term, concept, or semantics of authority. Third-party semantic models and instrumentation may be useful inputs or interoperable systems, but should not be conflated with mechanical enforcement. Architectural alignment does not imply identical scope, partnership, or endorsement.

## Falsification / conformance candidates

- Semantically well-described mandate that is expired or revoked: DENY.
- Agent self-asserted authority without trusted delegation: DENY.
- Authorization for action A reused for altered action B: DENY.
- Direct tool or API route bypassing the enforcement point: effect must be blocked within the specified trust boundary.
- Same authority contract across distinct runtimes: consistent decision semantics and verifiable evidence, subject to declared environment assumptions.

## Scope and caveats

These are target invariants to be tested, not blanket claims of presently proven coverage on all execution surfaces. Any enforcement guarantee is conditional on the configured and tested trust boundary. No private correspondence or proprietary material is incorporated here.

This note is about the open contract; private enterprise implementations and VALO product IP remain outside its scope.

Reference: https://heimel.xyz
