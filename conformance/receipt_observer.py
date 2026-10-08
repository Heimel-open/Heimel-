"""Separate SQLite read path for committed effects and decision evidence."""
import sqlite3

def observe_receipt_evidence(path,permit):
    with sqlite3.connect(path) as db:
        row=db.execute('''SELECT j.permit_id,j.decision_id,j.issued_version,j.commit_version,
                           e.effect_id,e.effect_hash,j.transaction_id,j.outcome,e.payload
                           FROM receipt_journal j JOIN durable_effects e
                           ON e.transaction_id=j.transaction_id AND e.permit_id=j.permit_id
                           WHERE j.permit_id=?''',(permit,)).fetchone()
    if row is None:return None
    keys=('permit_id','decision_id','issued_authority_version','commit_authority_version',
          'effect_id','effect_hash','transaction_id','outcome','payload')
    return dict(zip(keys,row))
