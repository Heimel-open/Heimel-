"""Standalone synthetic race adapter, not the HEIMEL reference adapter.

SQLite transactions provide an actual persistent effect boundary. A separate
process performs restart recovery. This is a public test fixture, not production.
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


def dbopen(path):
    db=sqlite3.connect(path, timeout=5, isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS effects (permit TEXT PRIMARY KEY, effect TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS log (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, detail TEXT)')
    return db

def log(db,kind,detail=''):
    db.execute('INSERT INTO log(kind,detail) VALUES (?,?)',(kind,detail))

def setstate(path,key,value):
    db=dbopen(path);db.execute('INSERT OR REPLACE INTO state VALUES (?,?)',(key,value));log(db,'UPDATE',key+':'+value);db.close()

def attempt(path,permit,effect,barrier=None,stale=False):
    if barrier:barrier.wait(timeout=5)
    db=dbopen(path)
    db.execute('BEGIN IMMEDIATE')
    try:
        authority=db.execute("SELECT value FROM state WHERE key='authority'").fetchone()[0]
        log(db,'AUTHORITY_READ',authority)
        if authority!='valid' and not stale:
            log(db,'DENY',authority)
        else:
            try:
                db.execute('INSERT INTO effects VALUES (?,?)',(permit,effect))
                log(db,'EFFECT',effect)
            except sqlite3.IntegrityError:log(db,'DENY','permit_reused')
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK');raise
    finally:db.close()

def resume(path,permit,effect):
    db=dbopen(path)
    log(db,'RESTART','separate_process')
    found=db.execute('SELECT effect FROM effects WHERE permit=?',(permit,)).fetchone()
    log(db,'RECOVER_EXISTING' if found else 'RECOVER_UNKNOWN_FAIL_CLOSED',permit)
    db.close()

def run(test, mutant=None):
    permit='permit-'+test['id'];effect='lamp-1:on';mode=test['mode'];inp=test['input']
    with tempfile.TemporaryDirectory(prefix='heimel-race-') as tmp:
        path=str(Path(tmp)/'state.db');db=dbopen(path);db.close();setstate(path,'authority','valid')
        errors=[]
        if mode=='concurrent':
            ops=inp.get('operations',[])
            if test['id'] in ('HCONF-065','HCONF-067','HCONF-068'):
                setstate(path,'authority','revoked')
                attempt(path,permit,effect,stale=(mutant=='stale_authority'))
            else:
                barrier=threading.Barrier(2)
                threads=[]
                def worker():
                    try:attempt(path,permit,effect,barrier)
                    except Exception as ex:errors.append(str(ex))
                threads=[threading.Thread(target=worker) for _ in range(2)]
                for t in threads:t.start()
                for t in threads:t.join(timeout=8)
                if any(t.is_alive() for t in threads):errors.append('thread timed out')
        else:
            steps=inp['steps']
            if 'commit' in steps or 'commit_unknown' in steps:attempt(path,permit,effect)
            db=dbopen(path);log(db,'CRASH_INJECTED',test['id']);db.close()
            proc=subprocess.run([sys.executable,__file__,'--resume',path,permit,effect],capture_output=True,text=True)
            if proc.returncode:errors.append(proc.stderr)
            if mutant=='blind_replay':attempt(path,'replayed-'+permit,effect)
        db=dbopen(path)
        trace=db.execute('SELECT seq,kind,detail FROM log ORDER BY seq').fetchall()
        effects=db.execute('SELECT permit,effect FROM effects').fetchall();db.close()
        effect_events=[x for x in trace if x[1]=='EFFECT']
        if len(effects)>1 or len(effect_events)>1:errors.append('multiple effects')
        if mode=='concurrent' and test['id'] in ('HCONF-065','HCONF-067','HCONF-068') and effects:errors.append('effect after authority invalidation')
        if mode=='recovery' and not any(x[1]=='RESTART' for x in trace):errors.append('restart not observed')
        if mode=='recovery' and any(x[1]=='EFFECT' for x in trace if x[0]>next(y[0] for y in trace if y[1]=='RESTART')):errors.append('blind replay')
        if mode=='concurrent' and test['id'] in ('HCONF-066','HCONF-069') and len([x for x in trace if x[1]=='AUTHORITY_READ'])<2:errors.append('second consumer not observed')
        return {'id':test['id'],'status':'FAIL' if errors else 'PASS','errors':errors,'trace':trace,'effect_count':len(effects)}

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--resume':resume(*sys.argv[2:5]);return
    root=Path(__file__).resolve().parent/'v0.2.0/vectors/runtime_adversarial.json'
    tests=json.loads(root.read_text())['tests']
    selected=[t for t in tests if t['mode'] in ('concurrent','recovery')]
    results=[run(t) for t in selected]
    negative={
      'stale_authority':[run(t,'stale_authority') for t in selected if t['id']=='HCONF-065'],
      'blind_replay':[run(t,'blind_replay') for t in selected if t['id']=='HCONF-075'],
    }
    output={'scope':'standalone synthetic SQLite adapter; not external/production conformance','results':results,'negative_controls':negative}
    print(json.dumps(output,indent=2))
    if any(x['status']!='PASS' for x in results) or any(x['status']!='FAIL' for v in negative.values() for x in v):sys.exit(1)
if __name__=='__main__':main()
