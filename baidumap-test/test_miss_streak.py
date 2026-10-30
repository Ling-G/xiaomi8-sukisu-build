import unittest
from baidumap_flow import MissStreak


class StopRuleTests(unittest.TestCase):
    def test_fifth_confirmed_miss_stops(self):
        state = MissStreak(5)
        self.assertEqual([state.record('not_found') for _ in range(5)],
                         [False, False, False, False, True])
        self.assertEqual(state.count, 5)

    def test_found_breaks_four_miss_streak(self):
        state = MissStreak(5)
        for _ in range(4):
            self.assertFalse(state.record('not_found'))
        self.assertFalse(state.record('opened'))
        self.assertEqual(state.count, 0)
        for _ in range(4):
            self.assertFalse(state.record('not_found'))
        self.assertTrue(state.record('not_found'))

    def test_operational_errors_are_not_search_misses(self):
        state = MissStreak(5)
        for _ in range(4):
            state.record('not_found')
        self.assertFalse(state.record('failed'))
        self.assertEqual(state.count, 0)
        self.assertFalse(state.record('not_found'))
        self.assertEqual(state.count, 1)


if __name__ == '__main__':
    unittest.main()
