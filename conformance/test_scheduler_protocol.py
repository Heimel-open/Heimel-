import unittest
from scheduler_protocol import SQLiteFixtureAdapter

class ProtocolTests(unittest.TestCase):
    def test_fresh_commit(self):
        a=SQLiteFixtureAdapter()
        try:
            a.issue('0',0);a.commit('0')
            self.assertEqual(a.observe(),{'p0':'effect-0'})
        finally:a.close()
    def test_stale_permit_rejected(self):
        a=SQLiteFixtureAdapter()
        try:
            a.issue('0',0);a.update(1);a.commit('0')
            self.assertEqual(a.observe(),{})
        finally:a.close()
    def test_mutant_exposes_effect(self):
        a=SQLiteFixtureAdapter(mutant=True)
        try:
            a.issue('0',0);a.update(1);a.commit('0')
            self.assertEqual(a.observe(),{'p0':'effect-0'})
        finally:a.close()

if __name__=='__main__':unittest.main()
