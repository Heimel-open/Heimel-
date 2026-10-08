"""Experimental observable effect harness. NOT a claim of external runtime conformance."""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE = HERE / 'v0.2.0'

def connect(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS effects (permit TEXT PRIMARY KEY, effect TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, permit TEXT NOT NULL)')
    return db

def emit(db, event, permit):
    db.execute('INSERT INTO events(event,permit) VALUES (?,?)', (event, permit))

def commit(path, permit, effect, barrier=None):
    db=connect(path)
    if barrier is not None: barrier.wait(timeout=5)
    db.execute('BEGIN IMMEDIATE')
    try:
        emit(db,'AUTHORITY_CHECK',permit)
        try:
            db.execute('INSERT INTO effects(permit,effect) VALUES (?,?)',(permit,effect))
            emit(db,'EFFECT_COMMITTED',permit)
        except sqlite3.IntegrityError:
            emit(db,'DUPLICATE_REJECTED',permit)
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK');raise
    finally: db.close()

def events(path):
    db=connect(path)
    rows=db.execute('SELECT seq,event,permit FROM events ORDER BY seq').fetchall()
    effects=db.execute('SELECT permit,effect FROM effects').fetchall()
    db.close()
    return rows,effects

def check_trace(rows,effects,permit,mode):
    errors=[]
    commits=[r for r in rows if r[1]=='EFFECT_COMMITTED' and r[2]==permit]
    checks=[r for r in rows if r[1]=='AUTHORITY_CHECK' and r[2]==permit]
    if len(commits)>1 or len(effects)>1:errors.append('more than one effect')
    if any(not any(c[0]<e[0] for c in checks) for e in commits):errors.append('effect without observed authority check')
    if mode=='concurrent' and len(checks)<2:errors.append('concurrency attempts not observed')
    if mode=='recovery' and not any(e[1]=='RESTART_OBSERVED' for e in rows):errors.append('restart not observed')
    return errors

def exercise(test):
    mode=test['mode'];permit='permit-'+test['id'];effect=test['input']['effect']['id']+':'+test['input']['effect']['action']
    with tempfile.TemporaryDirectory(prefix='heimel-observed-') as tmp:
        path=str(Path(tmp)/'journal.db');db=connect(path);db.close()
        if mode=='concurrent':
            barrier=threading.Barrier(2)
            errors=[]
            def worker():
                try:commit(path,permit,effect,barrier)
                except Exception as exc:errors.append(str(exc))
            threads=[threading.Thread(target=worker) for _ in range(2)]
            for t in threads:t.start()
            for t in threads:t.join(timeout=8)
            if any(t.is_alive() for t in threads):errors.append('thread timed out')
        else:
            steps=test['input']['steps']
            db=connect(path)
            emit(db,'AUTHORITY_CHECK',permit)
            if 'commit' in steps or 'commit_unknown' in steps:
                db.execute('INSERT INTO effects VALUES (?,?)',(permit,effect))
                emit(db,'EFFECT_COMMITTED',permit)
            emit(db,'CRASH_INJECTED',permit)
            db.close()
            # Separate process, same durable journal. Recovery must not blindly execute.
            p=subprocess.run([sys.executable,__file__,'--resume',path,permit,effect],capture_output=True,text=True)
            errors=[] if p.returncode==0 else [p.stderr.strip() or 'restart failed']
        rows,effects=events(path)
        errors+=check_trace(rows,effects,permit,mode)
        return {'id':test['id'],'status':'PASS' if not errors else 'FAIL','errors':errors,'trace':rows,'effects':effects,
                'trace_sha256':hashlib.sha256(json.dumps([rows,effects],separators=(',',':')).encode()).hexdigest()}

def resume(path,permit,effect):
    db=connect(path)
    emit(db,'RESTART_OBSERVED',permit)
    found=db.execute('SELECT effect FROM effects WHERE permit=?',(permit,)).fetchone()
    emit(db,'RECOVER_EXISTING' if found else 'RECOVER_NO_REPLAY',permit)
    db.close()

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--resume':
        resume(*sys.argv[2:5]);return
    doc=json.loads((SUITE/'vectors/runtime_adversarial.json').read_text())
    results=[exercise(t) for t in doc['tests'] if t['mode'] in ('concurrent','recovery')]
    print(json.dumps({'status':'PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',
        'scope':'synthetic SQLite harness only; not external adapter', 'results':results},indent=2))
    if any(x['status']!='PASS' for x in results):sys.exit(1)
if __name__=='__main__':main()
