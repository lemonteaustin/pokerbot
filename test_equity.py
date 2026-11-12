"""Offline equity artifact and chart sanity checks."""
import unittest

from push_fold_chart import SHOVE, CALL


class ChartTests(unittest.TestCase):
    def test_chart_axes_and_monotonic_short_stack_expansion(self):
        self.assertEqual(len(SHOVE), 15 * 5 * 8)
        for position in ('early', 'cutoff', 'button', 'small_blind', 'big_blind'):
            for behind in range(8):
                for bb in range(1, 15):
                    self.assertTrue(SHOVE[bb + 1, position, behind] <= SHOVE[bb, position, behind])
                for bb in range(1, 16):
                    self.assertIn('AA', SHOVE[bb, position, behind])
        for bb in range(1, 16):
            for behind in range(7):
                self.assertTrue(CALL[bb, behind + 1] <= CALL[bb, behind])

    def test_equity_artifact(self):
        try:
            from preflop_equity import EQUITY, SAMPLES
        except ImportError:
            self.skipTest('equity artifact not installed yet')
        self.assertEqual(len(EQUITY), 169)
        self.assertGreaterEqual(SAMPLES, 20000)
        for row in EQUITY.values():
            self.assertEqual(len(row), 5)
            self.assertTrue(all(0 < value < 1 for value in row))
        self.assertGreater(EQUITY['AA'][0], .83)
        self.assertLess(EQUITY['72o'][0], .37)
        self.assertGreater(EQUITY['AKs'][0], EQUITY['AKo'][0])


if __name__ == '__main__':
    unittest.main()
