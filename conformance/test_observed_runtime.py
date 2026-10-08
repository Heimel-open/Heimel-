"""Negative controls for experimental observation harness."""
import unittest
import observed_runtime as harness

class TraceGateTests(unittest.TestCase):
    def test_rejects_duplicate_effect(self):
        rows=[(1,'AUTHORITY_CHECK','p'),(2,'EFFECT_COMMITTED','p'),(3,'EFFECT_COMMITTED','p')]
        self.assertIn('more than one effect',harness.check_trace(rows,[('p','x'),('p','x')],'p','concurrent'))
    def test_rejects_unchecked_effect(self):
        self.assertIn('effect without observed authority check',harness.check_trace([(1,'EFFECT_COMMITTED','p')],[('p','x')],'p','single'))
    def test_rejects_fake_concurrency(self):
        self.assertIn('concurrency attempts not observed',harness.check_trace([(1,'AUTHORITY_CHECK','p'),(2,'EFFECT_COMMITTED','p')],[('p','x')],'p','concurrent'))
    def test_rejects_fake_recovery(self):
        self.assertIn('restart not observed',harness.check_trace([(1,'AUTHORITY_CHECK','p')],[],'p','recovery'))

if __name__=='__main__':unittest.main()
