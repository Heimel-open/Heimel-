"""Production proof profile: offline verification and fail-closed gate.

No external adapter is bundled. Fixture results never certify production.
"""
import hashlib
import hmac
import json
from pathlib import Path

REQUIRED=('manifest','schedule','authority','effects','receipts','recovery')
GATES=('external_adapter','attestation','recovery','coverage','offline_replay')

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def verify_bundle(bundle, trusted_keys=None):
    trusted_keys=trusted_keys or {}
    missing=[name for name in REQUIRED if name not in bundle]
    if missing:return {'status':'INCOMPLETE','reason':'missing artifacts','missing':missing}
    manifest=bundle['manifest']
    if manifest.get('environment')!='production' or not manifest.get('external_adapter_id'):
        return {'status':'INCOMPLETE','reason':'no identified production adapter'}
    if not isinstance(bundle.get('gates'),dict):
        return {'status':'INCOMPLETE','reason':'missing gate evidence'}
    hashes=manifest.get('artifact_hashes',{})
    for name in REQUIRED:
        if name=='manifest':continue
        if name not in hashes:return {'status':'INCOMPLETE','reason':'missing artifact hash','artifact':name}
        if not hmac.compare_digest(str(hashes[name]),digest(bundle[name])):
            return {'status':'FAIL','reason':'artifact hash mismatch','artifact':name}
    signature=bundle.get('attestation')
    if not signature:return {'status':'INCOMPLETE','reason':'missing signed attestation'}
    key_id=signature.get('key_id')
    if key_id not in trusted_keys:return {'status':'INCOMPLETE','reason':'untrusted or missing verification key'}
    # HMAC is intentionally a test-only verification primitive; it is not
    # sufficient for third-party production attestation or hardware identity.
    if signature.get('algorithm')!='HMAC-SHA256-TEST-ONLY':
        return {'status':'INCOMPLETE','reason':'production signature verifier not configured'}
    mac=hmac.new(trusted_keys[key_id],canonical({'manifest':manifest,'gates':bundle['gates']}),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac,str(signature.get('signature',''))):
        return {'status':'FAIL','reason':'attestation mismatch'}
    statuses=[bundle['gates'].get(g,'INCOMPLETE') for g in GATES]
    if any(s=='FAIL' for s in statuses):return {'status':'FAIL','reason':'failed production gate'}
    if any(s!='PASS' for s in statuses):return {'status':'INCOMPLETE','reason':'unproven production gate'}
    # No production signing algorithm is implemented; never certify a test MAC.
    return {'status':'INCOMPLETE','reason':'test-only MAC cannot establish production attestation'}

def verify_directory(path, trusted_keys=None):
    root=Path(path)
    bundle={}
    for name in REQUIRED:
        file=root/(name+'.json')
        if file.exists():bundle[name]=json.loads(file.read_text())
    for name in ('gates','attestation'):
        file=root/(name+'.json')
        if file.exists():bundle[name]=json.loads(file.read_text())
    return verify_bundle(bundle,trusted_keys)
