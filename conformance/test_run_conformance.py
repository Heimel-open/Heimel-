from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "conformance" / "run_conformance.py")
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)

def test_indeterminate_when_required_observation_missing():
    t={"expect":{"decision_not":"ALLOW","effect_may_execute":False}}
    status, errors=runner.evaluate(t, {"decision":"DENY"})
    assert status=="INDETERMINATE"
    assert any("effect_executed" in e for e in errors)

def test_fail_when_denied_effect_executes():
    t={"expect":{"decision_not":"ALLOW","effect_may_execute":False}}
    status, errors=runner.evaluate(t, {"decision":"DENY","effect_executed":True})
    assert status=="FAIL"

def test_one_shot_count():
    t={"expect":{"max_effect_count":1}}
    status, errors=runner.evaluate(t, {"effect_count":2})
    assert status=="FAIL"

def test_pass_when_complete_fail_closed():
    t={"expect":{"decision_not":"ALLOW","effect_may_execute":False}}
    status, errors=runner.evaluate(t, {"decision":"DENY","effect_executed":False})
    assert status=="PASS"

if __name__=="__main__":
    for f in [test_indeterminate_when_required_observation_missing,test_fail_when_denied_effect_executes,test_one_shot_count,test_pass_when_complete_fail_closed]:
        f()
    print("PASS: conformance runner self-tests")
