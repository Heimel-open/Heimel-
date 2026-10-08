"""SQLite fixture adapter with atomic effect, decision evidence and receipt binding."""
import sqlite3
import tempfile
from pathlib import Path
from receipt_contract import digest,verify_receipt
from receipt_observer import observe_receipt_evidence

class SQLiteFixtureAdapter:
    def __init__(self,mutant=False):
        self.tmp=tempfile.TemporaryDirectory(prefix='heimel-adapter-protocol-')
        self.path=str(Path(self.tmp.name)/'effects.db')
        self.mutant=mutant
        self.reset()
    def reset(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS durable_effects (permit_id TEXT PRIMARY KEY,effect_id TEXT,payload TEXT,effect_hash TEXT,transaction_id TEXT UNIQUE)')
            db.execute('CREATE TABLE IF NOT EXISTS receipt_journal (permit_id TEXT PRIMARY KEY,decision_id TEXT,issued_version INTEGER,commit_version INTEGER,transaction_id TEXT UNIQUE,outcome TEXT)')
            db.execute('DELETE FROM durable_effects')
            db.execute('DELETE FROM receipt_journal')
        self.version=0;self.issued={};self.receipts={}
    def issue(self,actor,version):
        if version!=self.version:raise ValueError('issued version mismatch')
        self.issued[actor]=version
    def update(self,version):
        if version!=self.version+1:raise ValueError('nonsequential authority update')
        self.version=version
    def commit(self,actor):
        permit='p'+actor
        fresh=self.issued[actor]==self.version and self.version<2
        if not (fresh or self.mutant):return
        payload='effect-'+actor;effect_id='e-'+permit;tx='tx-'+permit
        h=digest({'permit_id':permit,'effect_id':effect_id,'payload':payload})
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT effect_hash FROM durable_effects WHERE permit_id=?',(permit,)).fetchone()
            if existing:
                if existing[0]!=h:raise ValueError('effect replay mismatch')
                return
            db.execute('INSERT INTO durable_effects VALUES (?,?,?,?,?)',(permit,effect_id,payload,h,tx))
            db.execute('INSERT INTO receipt_journal VALUES (?,?,?,?,?,?)',(permit,'d-'+permit,self.issued[actor],self.version,tx,'COMMITTED'))
        self.receipts[actor]=dict(permit_id=permit,decision_id='d-'+permit,
                                  issued_authority_version=self.issued[actor],commit_authority_version=self.version,
                                  effect_id=effect_id,effect_hash=h,transaction_id=tx,outcome='COMMITTED')
    def receipt(self,actor):
        receipt=self.receipts.get(actor)
        if receipt is None:return {'status':'DENIED'}
        return verify_receipt(receipt,observe_receipt_evidence(self.path,'p'+actor))
    def observe(self):
        with sqlite3.connect(self.path) as db:
            return dict(db.execute('SELECT permit_id,payload FROM durable_effects'))
    def close(self):self.tmp.cleanup()
