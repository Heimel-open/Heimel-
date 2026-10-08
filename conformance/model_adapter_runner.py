"""Bounded model-to-fixture replay with explicit incomplete status.

A separate SQLite connection observes durable effects. This is NOT an external
adapter contract or complete history exploration. The bound applies to replayed
terminal histories; exceeding it returns INCOMPLETE rather than PASS.
"""
import argparse
import json
import sqlite3
import tempfile
from collections import deque
from pathlib import Path
from multi_permit_explorer import INITIAL,successors
from scheduler_protocol import SQLiteFixtureAdapter


def enumerate_schedules():
    # Breadth-first traversal of complete histories. No state deduplication:
    # different schedules reaching the same state are intentionally retained.
    queue=deque([(INITIAL,())])
    while queue:
        state,trace=queue.popleft()
        moves=list(successors(state))
        if not moves:
            yield trace
        for action,new,unsafe in moves:
            if unsafe:raise AssertionError('unsafe reference model')
            queue.append((new,trace+(action,)))


def observe(path):
    with sqlite3.connect(path) as conn:
        return dict(conn.execute('SELECT permit,effect FROM effects'))


def replay(schedule,mutant=False,adapter_factory=None):
    adapter=(adapter_factory or SQLiteFixtureAdapter)(mutant=mutant)
    try:
        version=0;issued={};expected={};receipt_failures=[]
        for step in schedule:
            if step.startswith('issue_'):
                actor=step[-1];issued[actor]=version;adapter.issue(actor,version)
            elif step.startswith('authority_version_'):
                version=int(step.rsplit('_',1)[1]);adapter.update(version)
            elif step.startswith(('commit_','deny_')):
                actor=step[-1];permit='p'+actor
                allowed=issued[actor]==version and version<2
                if allowed:expected[permit]='effect-'+actor
                adapter.commit(actor)
            elif step.startswith('receipt_'):
                actor=step[-1]
                outcome=adapter.receipt(actor)
                should_commit=('p'+actor) in expected
                required='PASS' if should_commit else 'DENIED'
                if outcome.get('status')!=required:
                    receipt_failures.append({'actor':actor,'required':required,'observed':outcome})
            else:raise ValueError(step)
        actual=adapter.observe()
        return {'status':'PASS' if actual==expected and not receipt_failures else 'FAIL','schedule':schedule,'expected':expected,'observed':actual,'receipt_failures':receipt_failures}
    finally:adapter.close()


def run(max_schedules=25):
    if max_schedules<1:raise ValueError('max_schedules must be positive')
    failures=[];mutant_caught=None;total=0
    # A terminal schedule beyond the budget means coverage is incomplete.
    iterator=enumerate_schedules()
    for schedule in iterator:
        if total>=max_schedules:
            return {'status':'INCOMPLETE','schedules':total,'budget':max_schedules,
                    'failures':failures[:5],'mutant_counterexample':mutant_caught,
                    'reason':'terminal schedule replay budget exceeded'}
        result=replay(schedule)
        total+=1
        if result['status']=='FAIL':failures.append(result)
        if mutant_caught is None:
            bad=replay(schedule,mutant=True)
            if bad['status']=='FAIL':mutant_caught=bad
    return {'status':'FAIL' if failures or mutant_caught is None else 'PASS',
            'schedules':total,'budget':max_schedules,'failures':failures[:5],
            'mutant_counterexample':mutant_caught,
            'scope':'isolated SQLite fixture; not an external adapter; no DPOR'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--max-schedules',type=int,default=25);a=p.parse_args()
    result=run(a.max_schedules);print(json.dumps(result,indent=2))
    if result['status']!='PASS':raise SystemExit(1)
