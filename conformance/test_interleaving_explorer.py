import unittest
import interleaving_explorer as model

class ExplorerTests(unittest.TestCase):
    def test_safe_model(self):
        result=model.explore()
        self.assertEqual(result['status'],'PASS')
        self.assertGreater(result['edges'],0)
    def test_stale_mutant_detected(self):
        result=model.explore(mutant=True)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(any('revoke' in x['trace'] for x in result['violations']))
    def test_budget_is_incomplete(self):
        self.assertEqual(model.explore(max_states=2)['status'],'INCOMPLETE')

if __name__=='__main__':unittest.main()
