"""Transactional receipt fixture; journal and effect committed atomically."""
import sqlite3
import tempfile
from pathlib import Path
from receipt_contract import digest
from receipt_observer import observe_receipt_evidence

class ReceiptFixture:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='heimel-receipt-')
        self.path=str(Path(self.tmp.name)/'receipt.db')
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE durable_effects (permit_id TEXT PRIMARY KEY,effect_id TEXT,payload TEXT,effect_hash TEXT,transaction_id TEXT UNIQUE)')
            db.execute('CREATE TABLE receipt_journal (permit_id TEXT PRIMARY KEY,decision_id TEXT,issued_version INTEGER,commit_version INTEGER,transaction_id TEXT UNIQUE,outcome TEXT)')
        self.receipts={}
    def commit(self,permit,issued_version,commit_version,payload):
        if issued_version!=commit_version:return None
        transaction_id='tx-'+permit;effect_id='e-'+permit;decision_id='d-'+permit
        effect_hash=digest({'permit_id':permit,'effect_id':effect_id,'payload':payload})
        receipt=dict(permit_id=permit,decision_id=decision_id,issued_authority_version=issued_version,
                     commit_authority_version=commit_version,effect_id=effect_id,effect_hash=effect_hash,
                     transaction_id=transaction_id,outcome='COMMITTED')
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT effect_hash FROM durable_effects WHERE permit_id=?',(permit,)).fetchone()
            if previous:
                if previous[0]!=effect_hash:raise ValueError('permit replay with different effect')
                return self.receipts[permit]
            db.execute('INSERT INTO durable_effects VALUES (?,?,?,?,?)',(permit,effect_id,payload,effect_hash,transaction_id))
            db.execute('INSERT INTO receipt_journal VALUES (?,?,?,?,?,?)',
                       (permit,decision_id,issued_version,commit_version,transaction_id,'COMMITTED'))
        self.receipts[permit]=receipt
        return receipt
    def observe(self,permit):
        return observe_receipt_evidence(self.path,permit)
    def close(self):self.tmp.cleanup()
