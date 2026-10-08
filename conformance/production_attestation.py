"""Ed25519 signature verification for offline production evidence bundles.

Trusted public keys must be provisioned out of band. No private keys are stored.
"""
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from production_proof import canonical


def verify_attestation(attestation, message, trusted_keys):
    if not attestation:
        return {'status':'INCOMPLETE','reason':'missing attestation'}
    if attestation.get('algorithm')!='Ed25519':
        return {'status':'INCOMPLETE','reason':'unsupported production signature algorithm'}
    key_id=attestation.get('key_id')
    if key_id not in trusted_keys:
        return {'status':'INCOMPLETE','reason':'key not provisioned in trust store'}
    try:
        key=Ed25519PublicKey.from_public_bytes(base64.b64decode(trusted_keys[key_id],validate=True))
        key.verify(base64.b64decode(attestation['signature'],validate=True),canonical(message))
    except (ValueError,KeyError,InvalidSignature,TypeError):
        return {'status':'FAIL','reason':'invalid Ed25519 attestation'}
    return {'status':'PASS'}
