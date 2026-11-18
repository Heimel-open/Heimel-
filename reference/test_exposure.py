"""Public cumulative exposure reference tests, independent of private code."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import tempfile
from pathlib import Path

from exposure import ExposureDenied, Ledger, Request


def denied(fn):
    try:
        fn()
    except ExposureDenied:
        return
    raise AssertionError("expected fail-closed refusal")


def case(request_id="a", **kw):
    return replace(Request(
        tenant="tenant", scope="shared-budget", dimension="money",
        unit="minor:NOK", request_id=request_id, amount=60,
        ceiling=100, now=1000, window=60,
    ), **kw)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Ledger(Path(tmp) / "budget.sqlite")
        assert ledger.reserve(case()) == "reserved"
        assert ledger.reserve(case()) == "reserved"
        denied(lambda: ledger.reserve(case("b", amount=41)))
        denied(lambda: ledger.reserve(case("a", amount=59)))
        assert ledger.reserve(case("b", amount=40)) == "reserved"
        ledger.transition("tenant", "a", "unknown")
        ledger.transition("tenant", "a", "unknown")
        ledger.transition("tenant", "b", "released")
        denied(lambda: ledger.reserve(case("b", amount=40)))
        denied(lambda: ledger.transition("tenant", "a", "released"))
        denied(lambda: ledger.reserve(case("late", now=5000, amount=41)))
        assert ledger.reserve(case("late", now=5000, amount=40)) == "reserved"
        assert ledger.reserve(case("other-tenant", tenant="other", amount=100)) == "reserved"
        assert ledger.reserve(case("other-unit", unit="minor:EUR", amount=100)) == "reserved"
        assert ledger.reserve(case("other-scope", scope="another", amount=100)) == "reserved"
        for invalid in (True, 1.5, -1):
            denied(lambda value=invalid: ledger.reserve(case("invalid", amount=value)))
        denied(lambda: ledger.reserve(case("invalid", window=0)))
        denied(lambda: ledger.reserve(case("invalid", ceiling=99.5)))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "concurrent.sqlite"
        Ledger(path)
        def reserve(i):
            try:
                return Ledger(path).reserve(case(f"concurrent-{i}", amount=35))
            except ExposureDenied:
                return "denied"
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(reserve, range(8)))
        assert outcomes.count("reserved") == 2, outcomes
        assert outcomes.count("denied") == 6, outcomes
        assert Ledger(path).state("tenant", "concurrent-0") in {"reserved", None}
    print("PASS: public reference cumulative exposure (scope, replay, unknown, concurrent writers)")


if __name__ == "__main__":
    main()
