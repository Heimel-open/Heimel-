import unittest
from itertools import islice
import model_adapter_runner as runner

class RunnerTests(unittest.TestCase):
    def test_normal_fixture_replays(self):
        plans=list(islice(runner.enumerate_schedules(),3))
        self.assertEqual(len(plans),3)
        for plan in plans:self.assertEqual(runner.replay(plan)['status'],'PASS')
    def test_mutant_is_observed(self):
        plans=list(islice(runner.enumerate_schedules(),25))
        self.assertTrue(any(runner.replay(p,mutant=True)['status']=='FAIL' for p in plans))
    def test_budget_reports_incomplete(self):
        self.assertEqual(runner.run(1)['status'],'INCOMPLETE')
    def test_reject_invalid_budget(self):
        with self.assertRaises(ValueError):runner.run(0)

if __name__=='__main__':unittest.main()
