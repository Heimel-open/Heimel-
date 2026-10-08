import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import unittest
from production_proof import REQUIRED,GATES,canonical,digest,verify_bundle

class ProofTests(unittest.TestCase):
    def bundle(self):
        b={k:{} for k in REQUIRED}
        b['manifest']={'environment':'production','external_adapter_id':'test-adapter'}
        b['manifest']['artifact_hashes']={k:digest(b[k]) for k in REQUIRED if k!='manifest'}
        b['gates']={k:'PASS' for k in GATES}
        self.key=Ed25519PrivateKey.generate()
        b['attestation']={'key_id':'test','algorithm':'Ed25519'}
        b['attestation']['signature']=base64.b64encode(self.key.sign(canonical({'manifest':b['manifest'],'gates':b['gates']}))).decode()
        return b
    def check(self,b):
        key=self.key.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        return verify_bundle(b,{'test':base64.b64encode(key).decode()})
    def test_signed_bundle_without_external_witness_incomplete(self):
        self.assertEqual(self.check(self.bundle())['status'],'INCOMPLETE')
    def test_missing_adapter_incomplete(self):
        b=self.bundle();b['manifest'].pop('external_adapter_id')
        self.assertEqual(self.check(b)['status'],'INCOMPLETE')
    def test_tampered_effect_fails(self):
        b=self.bundle();b['effects']={'changed':True}
        self.assertEqual(self.check(b)['status'],'FAIL')
    def test_bad_signature_fails(self):
        b=self.bundle();b['attestation']['signature']=base64.b64encode(b'0'*64).decode()
        self.assertEqual(self.check(b)['status'],'FAIL')
    def test_known_fail_precedence(self):
        b=self.bundle();b['gates']['recovery']='FAIL';b['gates']['coverage']='INCOMPLETE'
        self.assertEqual(self.check(b)['status'],'FAIL')
    def test_missing_artifact_incomplete(self):
        b=self.bundle();b.pop('recovery')
        self.assertEqual(self.check(b)['status'],'INCOMPLETE')

if __name__=='__main__':unittest.main()
