import hashlib
import hmac
import unittest
from production_proof import REQUIRED,GATES,canonical,digest,verify_bundle

class ProofTests(unittest.TestCase):
    def bundle(self):
        b={k:{} for k in REQUIRED}
        b['manifest']={'environment':'production','external_adapter_id':'test-adapter'}
        b['manifest']['artifact_hashes']={k:digest(b[k]) for k in REQUIRED if k!='manifest'}
        b['gates']={k:'PASS' for k in GATES}
        b['attestation']={'key_id':'test','algorithm':'HMAC-SHA256-TEST-ONLY'}
        b['attestation']['signature']=hmac.new(b'secret',canonical({'manifest':b['manifest'],'gates':b['gates']}),hashlib.sha256).hexdigest()
        return b
    def check(self,b):return verify_bundle(b,{'test':b'secret'})
    def test_test_only_signature_never_passes_production(self):
        self.assertEqual(self.check(self.bundle())['status'],'INCOMPLETE')
    def test_missing_adapter_incomplete(self):
        b=self.bundle();b['manifest'].pop('external_adapter_id')
        self.assertEqual(self.check(b)['status'],'INCOMPLETE')
    def test_tampered_effect_fails(self):
        b=self.bundle();b['effects']={'changed':True}
        self.assertEqual(self.check(b)['status'],'FAIL')
    def test_bad_signature_fails(self):
        b=self.bundle();b['attestation']['signature']='0'*64
        self.assertEqual(self.check(b)['status'],'FAIL')
    def test_known_fail_precedence(self):
        b=self.bundle();b['gates']['recovery']='FAIL';b['gates']['coverage']='INCOMPLETE'
        self.assertEqual(self.check(b)['status'],'FAIL')
    def test_missing_artifact_incomplete(self):
        b=self.bundle();b.pop('recovery')
        self.assertEqual(self.check(b)['status'],'INCOMPLETE')

if __name__=='__main__':unittest.main()
