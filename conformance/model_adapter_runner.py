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
from race_adapter import dbopen,setstate


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


def replay(schedule,mutant=False):
    with tempfile.TemporaryDirectory(prefix='heimel-model-adapter-') as tmp:
        path=str(Path(tmp)/'effects.db');db=dbopen(path);db.close()
        setstate(path,'authority','valid')
        version=0;issued={};expected={}
        for step in schedule:
            if step.startswith('issue_'):
                issued[step[-1]]=version
            elif step.startswith('authority_version_'):
                version=int(step.rsplit('_',1)[1])
                setstate(path,'authority','revoked' if version==2 else 'valid')
            elif step.startswith(('commit_','deny_')):
                actor=step[-1];permit='p'+actor
                allowed=issued[actor]==version and version<2
                if allowed:expected[permit]='effect-'+actor
                db=dbopen(path)
                db.execute('BEGIN IMMEDIATE')
                try:
                    # This fixture executes an isolated transactional effect.
                    # Mutant deliberately ignores the authority/version check.
                    if allowed or mutant:
                        db.execute('INSERT OR IGNORE INTO effects VALUES (?,?)',(permit,'effect-'+actor))
                    db.execute('COMMIT')
                except BaseException:
                    db.execute('ROLLBACK');raise
                finally:db.close()
            elif step.startswith('receipt_'):
                pass
            else:raise ValueError(step)
        actual=observe(path)
        return {'status':'PASS' if actual==expected else 'FAIL','schedule':schedule,'expected':expected,'observed':actual}


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
