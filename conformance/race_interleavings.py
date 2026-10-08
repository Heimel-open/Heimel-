"""Deterministic race scheduler and independent durable-state observation.
Exercises authority mutation before/after commit and stale-read injection.
"""
import json
import sqlite3
import tempfile
import threading
from pathlib import Path
from race_adapter import attempt,dbopen,log,setstate


def observe(path):
    # Independent connection: inspect committed effects, not adapter claims.
    db=sqlite3.connect(path)
    effects=db.execute('SELECT permit,effect FROM effects ORDER BY permit').fetchall()
    history=db.execute('SELECT seq,kind,detail FROM log ORDER BY seq').fetchall()
    db.close()
    return effects,history

def scenario(order,stale=False):
    with tempfile.TemporaryDirectory(prefix='heimel-schedule-') as tmp:
        path=str(Path(tmp)/'state.db');db=dbopen(path);db.close()
        setstate(path,'authority','valid')
        permit='permit-A';effect='lamp-1:on'
        errors=[]
        if order=='revoke_before_commit':
            setstate(path,'authority','revoked')
            attempt(path,permit,effect,stale=stale)
        elif order=='commit_before_revoke':
            attempt(path,permit,effect)
            setstate(path,'authority','revoked')
        elif order=='two_consumers':
            barrier=threading.Barrier(2)
            def consume():
                try:attempt(path,permit,effect,barrier)
                except Exception as e:errors.append(str(e))
            a=threading.Thread(target=consume);b=threading.Thread(target=consume)
            a.start();b.start();a.join(timeout=8);b.join(timeout=8)
            if a.is_alive() or b.is_alive():errors.append('consumer timeout')
        else:raise ValueError(order)
        effects,history=observe(path)
        if len(effects)>1:errors.append('duplicate committed effects')
        if order=='revoke_before_commit' and effects:errors.append('committed under revoked authority')
        if order=='commit_before_revoke' and len(effects)!=1:errors.append('authorized commit missing')
        if order=='two_consumers' and len(effects)!=1:errors.append('one-permit invariant violated')
        if not any(x[1]=='AUTHORITY_READ' for x in history):errors.append('no observed authority read')
        return {'schedule':order,'mutant':stale,'status':'FAIL' if errors else 'PASS','errors':errors,'effects':effects,'trace':history}

def main():
    cases=[scenario(x) for x in ('revoke_before_commit','commit_before_revoke','two_consumers')]
    mutant=scenario('revoke_before_commit',stale=True)
    print(json.dumps({'cases':cases,'mutant':mutant,'scope':'synthetic SQLite scheduling; not exhaustive interleavings'},indent=2))
    if any(x['status']!='PASS' for x in cases) or mutant['status']!='FAIL':raise SystemExit(1)
if __name__=='__main__':main()
