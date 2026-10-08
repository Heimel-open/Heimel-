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
    statuses=[bundle['gates'].get(g,'INCOMPLETE') for g in GATES]
    if any(s=='FAIL' for s in statuses):return {'status':'FAIL','reason':'failed production gate'}
    # A signature over the full evidence manifest is necessary, not sufficient:
    # every required gate must also have independently checkable evidence.
    from production_attestation import verify_attestation
    signature=verify_attestation(bundle.get('attestation'),
        {'manifest':manifest,'gates':bundle['gates']},trusted_keys)
    if signature['status']!='PASS':return signature
    statuses=[bundle['gates'].get(g,'INCOMPLETE') for g in GATES]
    if any(s=='FAIL' for s in statuses):return {'status':'FAIL','reason':'failed production gate'}
    if any(s!='PASS' for s in statuses):return {'status':'INCOMPLETE','reason':'unproven production gate'}
    # Do not trust self-declared PASS values from a signed bundle. A production
    # observer must attest actual external effect/recovery evidence separately.
    return {'status':'INCOMPLETE','reason':'external effect and recovery witnesses not verified'}

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
