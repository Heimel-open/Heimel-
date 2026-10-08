import unittest
from receipt_fixture import ReceiptFixture
from receipt_contract import verify_receipt

class ReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.f=ReceiptFixture()
        self.r=self.f.commit('p0',1,1,'effect-0')
        self.e=self.f.observe('p0')
    def tearDown(self):self.f.close()
    def test_valid(self):self.assertEqual(verify_receipt(self.r,self.e)['status'],'PASS')
    def test_swap_permit(self):
        r=dict(self.r,permit_id='p1')
        self.assertEqual(verify_receipt(r,self.e)['status'],'FAIL')
    def test_version_substitution(self):
        r=dict(self.r,commit_authority_version=2)
        self.assertEqual(verify_receipt(r,self.e)['status'],'FAIL')
    def test_phantom(self):
        self.assertEqual(verify_receipt(self.r,None)['status'],'INCOMPLETE')
    def test_effect_substitution(self):
        with __import__('sqlite3').connect(self.f.path) as db:
            db.execute('UPDATE durable_effects SET payload=? WHERE permit_id=?',('tampered','p0'))
        self.assertEqual(verify_receipt(self.r,self.f.observe('p0'))['status'],'FAIL')
    def test_duplicate_permit_effect(self):
        with self.assertRaises(ValueError):self.f.commit('p0',1,1,'other')
    def test_replay_same_effect(self):
        self.assertEqual(self.f.commit('p0',1,1,'effect-0'),self.r)
    def test_stale_denied(self):
        self.assertIsNone(self.f.commit('p1',0,1,'effect-1'))
        self.assertIsNone(self.f.observe('p1'))

if __name__=='__main__':unittest.main()
