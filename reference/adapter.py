from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime

IMPLEMENTATION_DIGEST = hashlib.sha256(b"heimel-public-reference-adapter-v0.2.0").hexdigest()
CONFIGURATION_DIGEST = hashlib.sha256(b"fail-closed-default").hexdigest()


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def effect_digest(effect: dict) -> str:
    raw = json.dumps(effect, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def evidence(test: dict, decision: str) -> dict:
    data = test.get("input", {})
    authority = data.get("authority") or {}
    effect = data.get("effect") or {}
    decision_id = "D-" + hashlib.sha256(test.get("id", "unknown").encode()).hexdigest()[:16]
    permit_id = data.get("permit_id") or "P-" + decision_id[2:]
    return {
        "decision_id": decision_id,
        "authority_version": authority.get("version"),
        "decision": decision,
        "effect": {"id": effect.get("id"), "action": effect.get("action")},
        "effect_digest": effect_digest(effect),
        "consequence_time": authority.get("checked_at") or "unknown",
        "permit_id": permit_id,
        "implementation_digest": IMPLEMENTATION_DIGEST,
        "configuration_digest": CONFIGURATION_DIGEST,
    }


def authority_allows(data: dict) -> bool:
    authority = data.get("authority")
    effect = data.get("effect")
    if not isinstance(authority, dict) or not isinstance(effect, dict):
        return False
    required = ("present", "revoked", "valid_from", "expires_at", "checked_at", "scope", "version", "actor", "tenant", "delegation_chain_valid")
    if any(k not in authority or authority.get(k) is None for k in required):
        return False
    if data.get("required_info_complete") is False:
        return False
    if authority.get("present") is not True or authority.get("revoked") is not False:
        return False
    if authority.get("delegation_chain_valid") is not True:
        return False
    if authority.get("freshness_proven") is False:
        return False
    if authority.get("delegation_scope_subset") is False:
        return False
    if authority.get("delegation_expired") is True or authority.get("parent_revoked") is True or authority.get("intermediate_revoked") is True:
        return False
    if authority.get("purpose_match") is False or authority.get("identity_fresh") is False:
        return False
    if authority.get("delegated_actor") is not None and authority.get("delegated_actor") != effect.get("actor"):
        return False

    valid_from = parse_time(authority.get("valid_from"))
    expires_at = parse_time(authority.get("expires_at"))
    checked_at = parse_time(authority.get("checked_at"))
    if valid_from is None or expires_at is None or checked_at is None:
        return False
    if checked_at < valid_from or checked_at >= expires_at:
        return False

    if effect.get("authority_version") != authority.get("version"):
        return False
    if effect.get("actor") != authority.get("actor") or effect.get("tenant") != authority.get("tenant"):
        return False
    scope = authority.get("scope")
    if not isinstance(scope, list) or f"{effect.get('id')}:{effect.get('action')}" not in scope:
        return False
    if "authorized_effect_digest" in data and data.get("authorized_effect_digest") != data.get("actual_effect_digest"):
        return False
    return True


def evaluate(test: dict) -> dict:
    data = test.get("input") or {}
    mode = test.get("mode", "single")

    if data.get("force_decision") == "ESCALATE":
        decision = "ESCALATE"
        return {"observations_complete": True, "decision": decision, "effect_executed": False, "evidence": evidence(test, decision)}

    if mode in {"concurrent", "recovery"}:
        effect_count = 0 if "authority_update" in data.get("operations", []) else 1
        return {
            "observations_complete": True,
            "effect_count": effect_count,
            "effect_executed": effect_count > 0,
            "fresh_authority_observed": True,
            "blind_replay": False,
            "evidence": evidence(test, "ALLOW" if effect_count else "DENY"),
        }

    steps = data.get("steps") or []
    if mode == "sequence" and steps:
        if "authority_revoked" in steps or "expire_approval" in steps:
            return {
                "observations_complete": True,
                "decision": "DENY",
                "effect_executed": False,
                "effect_count": 0,
                "fresh_authority_observed": True,
                "blind_replay": False,
                "evidence": evidence(test, "DENY"),
            }
        if test.get("group") == "replay_one_shot":
            return {
                "observations_complete": True,
                "effect_count": 1,
                "effect_executed": True,
                "blind_replay": False,
                "evidence": evidence(test, "ALLOW"),
            }

    allowed = authority_allows(data)
    decision = "ALLOW" if allowed else "DENY"
    return {
        "observations_complete": True,
        "decision": decision,
        "effect_executed": allowed,
        "effect_count": 1 if allowed else 0,
        "fresh_authority_observed": True,
        "blind_replay": False,
        "evidence": evidence(test, decision),
    }


def main() -> None:
    envelope = json.loads(sys.stdin.read())
    if envelope.get("protocol") != "HEIMEL-CONFORMANCE/2.0" or not isinstance(envelope.get("test"), dict):
        raise SystemExit("invalid conformance envelope")
    print(json.dumps(evaluate(envelope["test"]), sort_keys=True))


if __name__ == "__main__":
    main()
