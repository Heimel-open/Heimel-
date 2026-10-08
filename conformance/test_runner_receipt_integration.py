import unittest
from scheduler_protocol import SQLiteFixtureAdapter
from model_adapter_runner import replay

class CorruptReceiptAdapter(SQLiteFixtureAdapter):
    def receipt(self,actor):
        result=super().receipt(actor)
        if result['status']=='PASS':return {'status':'FAIL','reason':'simulated corrupted receipt'}
        return result

class ReceiptIntegrationTests(unittest.TestCase):
    def test_valid_receipt_schedule(self):
        plan=('issue_0','commit_0','receipt_0')
        self.assertEqual(replay(plan)['status'],'PASS')
    def test_corrupt_receipt_fails_runner(self):
        plan=('issue_0','commit_0','receipt_0')
        result=replay(plan,adapter_factory=CorruptReceiptAdapter)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(len(result['receipt_failures']),1)
    def test_denied_receipt(self):
        plan=('issue_0','authority_version_1','deny_0','receipt_0')
        self.assertEqual(replay(plan)['status'],'PASS')

if __name__=='__main__':unittest.main()
