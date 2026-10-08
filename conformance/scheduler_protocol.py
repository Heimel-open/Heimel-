"""Explicit adapter protocol for deterministic model schedule replay.

An adapter must implement reset(), issue(actor, version), update(version),
commit(actor), receipt(actor), observe(). observe() must read durable effects
independently of adapter return values. This module supplies a SQLite fixture.
"""
import sqlite3
import tempfile
from pathlib import Path
from race_adapter import dbopen,setstate

class SQLiteFixtureAdapter:
    def __init__(self,mutant=False):
        self.tmp=tempfile.TemporaryDirectory(prefix='heimel-adapter-protocol-')
        self.path=str(Path(self.tmp.name)/'effects.db')
        self.mutant=mutant
        self.reset()
    def reset(self):
        db=dbopen(self.path)
        db.execute('DELETE FROM effects')
        db.execute('DELETE FROM state')
        db.close()
        setstate(self.path,'authority','valid')
        self.version=0
        self.issued={}
    def issue(self,actor,version):
        if version!=self.version:raise ValueError('issued version mismatch')
        self.issued[actor]=version
    def update(self,version):
        if version!=self.version+1:raise ValueError('nonsequential authority update')
        self.version=version
        setstate(self.path,'authority','revoked' if version>=2 else 'valid')
    def commit(self,actor):
        permit='p'+actor
        db=dbopen(self.path)
        db.execute('BEGIN IMMEDIATE')
        try:
            fresh=self.issued[actor]==self.version and self.version<2
            if fresh or self.mutant:
                db.execute('INSERT OR IGNORE INTO effects VALUES (?,?)',(permit,'effect-'+actor))
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK');raise
        finally:db.close()
    def receipt(self,actor):
        pass  # fixture does not yet verify receipts
    def observe(self):
        with sqlite3.connect(self.path) as independent:
            return dict(independent.execute('SELECT permit,effect FROM effects'))
    def close(self):
        self.tmp.cleanup()
