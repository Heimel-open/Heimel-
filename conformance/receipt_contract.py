"""Independent receipt verification for the SQLite conformance fixture.

Hash binding detects accidental or adversarial substitution only when the
journal/effect observation is independently trusted. No signing is claimed.
"""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_receipt(receipt, evidence):
    if receipt is None:return {'status':'INCOMPLETE','reason':'missing receipt'}
    if evidence is None:return {'status':'INCOMPLETE','reason':'missing independent evidence'}
    required=('permit_id','decision_id','issued_authority_version','commit_authority_version',
              'effect_id','effect_hash','transaction_id','outcome')
    if any(k not in receipt for k in required):return {'status':'FAIL','reason':'missing binding field'}
    if any(receipt[k]!=evidence.get(k) for k in required):return {'status':'FAIL','reason':'receipt/evidence mismatch'}
    if receipt['outcome']!='COMMITTED':return {'status':'FAIL','reason':'not a committed receipt'}
    if receipt['issued_authority_version']!=receipt['commit_authority_version']:
        return {'status':'FAIL','reason':'stale authority'}
    if receipt['effect_hash']!=digest({'permit_id':receipt['permit_id'],'effect_id':receipt['effect_id'],
                                     'payload':evidence.get('payload')}):
        return {'status':'FAIL','reason':'effect digest mismatch'}
    return {'status':'PASS'}
