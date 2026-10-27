"""National end-of-day forecast from curated hourly history."""
import unittest

from scripts.national_forecast import (
    backtest,
    estimate_at_hour,
    forecast_scenarios,
    load_history,
    time_to_minutes,
)


class NationalForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history()

    def test_complete_elections_with_points(self):
        elections = self.history['elections']
        complete = {
            eid: e for eid, e in elections.items()
            if e.get('final_turnout_pct') is not None
        }
        # At least the five curated completed elections remain usable for remaining-pp.
        self.assertGreaterEqual(len(complete), 5)
        for eid, e in complete.items():
            self.assertGreaterEqual(len(e['points']), 6, eid)
            self.assertTrue(all(p.get('verified') for p in e['points']))
        # In-progress election day may appear without a final yet.
        live = elections.get('2026-10')
        if live is not None:
            self.assertIsNone(live.get('final_turnout_pct'))
            self.assertGreaterEqual(len(live.get('points') or []), 1)
            self.assertTrue(all(p.get('verified') for p in live['points']))

    def test_exact_match_no_invention(self):
        e = self.history['elections']['2022-11']
        est = estimate_at_hour(e, time_to_minutes('10:00'))
        self.assertEqual(est['method'], 'exact')
        self.assertAlmostEqual(est['turnout_pct'], 15.9, places=5)
        self.assertFalse(est['interpolated'])

    def test_interpolation_marked(self):
        e = self.history['elections']['2022-11']
        est = estimate_at_hour(e, time_to_minutes('11:00'))
        self.assertIsNotNone(est)
        self.assertTrue(est['interpolated'])
        self.assertEqual(est['method'], 'linear_interpolation')
        self.assertAlmostEqual(est['turnout_pct'], (15.9 + 28.4) / 2, places=5)

    def test_no_extrapolation(self):
        e = self.history['elections']['2022-11']
        self.assertIsNone(estimate_at_hour(e, time_to_minutes('08:00')))
        self.assertIsNone(estimate_at_hour(e, time_to_minutes('23:30')))

    def test_scenario_a_morning(self):
        fc = forecast_scenarios(12.5, time_to_minutes('10:00'), self.history)
        self.assertTrue(fc['ok'])
        self.assertEqual(fc['n'], 5)
        self.assertGreater(fc['mid'], 60)
        self.assertLess(fc['mid'], 75)
        self.assertLessEqual(fc['lo'], fc['mid'])
        self.assertLessEqual(fc['mid'], fc['hi'])
        self.assertAlmostEqual(fc['mid'], sum(s['forecast_pct'] for s in fc['scenarios']) / 5, places=6)

    def test_scenario_updates_with_hour(self):
        morning = forecast_scenarios(12.5, time_to_minutes('10:00'), self.history)
        noon = forecast_scenarios(27.4, time_to_minutes('12:00'), self.history)
        self.assertTrue(morning['ok'] and noon['ok'])
        self.assertNotAlmostEqual(morning['mid'], noon['mid'], places=1)

    def test_missing_election_reduces_n(self):
        hist = {
            **self.history,
            'elections': {k: v for k, v in self.history['elections'].items() if k != '2021-03'},
        }
        # remove 10:00 from another election to force skip? just using 4 elections is enough if min=3
        fc = forecast_scenarios(12.5, time_to_minutes('10:00'), hist)
        self.assertTrue(fc['ok'])
        self.assertEqual(fc['n'], 4)

    def backtest_mae_reasonable(self):
        bt = backtest(self.history)
        self.assertGreaterEqual(bt['n'], 20)
        self.assertLess(bt['mae'], 2.5)

    def test_backtest_mae_reasonable(self):
        self.backtest_mae_reasonable()


if __name__ == '__main__':
    unittest.main()
