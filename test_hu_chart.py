"""Published no-ante chart examples and exceptional ranges."""
import unittest
from hu_nash import PUSH_LIMITS, CALL_LIMITS, PUSH_INTERVALS


class HeadsUpChartTests(unittest.TestCase):
    def test_all_starting_classes_present(self):
        self.assertEqual(len(PUSH_LIMITS), 169)
        self.assertEqual(set(PUSH_LIMITS), set(CALL_LIMITS))

    def test_source_worked_example(self):
        # Source's T3s push / Q2o fold at six effective BB.
        self.assertEqual(PUSH_LIMITS['T3s'], 7.7)
        self.assertEqual(CALL_LIMITS['Q2o'], 5.6)
        self.assertGreater(PUSH_LIMITS['T3s'], 6)
        self.assertLess(CALL_LIMITS['Q2o'], 6)

    def test_nonmonotone_exception_preserved(self):
        allowed = lambda depth: any(lo <= depth <= hi for lo, hi in PUSH_INTERVALS['63s'])
        self.assertTrue(allowed(2))
        self.assertFalse(allowed(4))
        self.assertTrue(allowed(6))
        self.assertFalse(allowed(8))


if __name__ == '__main__':
    unittest.main()
