"""Official weighted historical turnout for the five primary groups."""
import unittest

from scripts.historical_turnout import (
    PRIMARY_GROUPS,
    YEARS,
    build_historical_comparison,
    build_insights,
    load_baseline_rows,
)


class HistoricalTurnoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_baseline_rows()
        cls.comparison = build_historical_comparison(cls.rows)

    def test_forty_four_active_primary_cities(self):
        self.assertEqual(self.comparison['active_n'], 44)
        self.assertTrue(self.comparison['coverage_complete'])

    def test_five_groups_three_years(self):
        self.assertEqual(tuple(self.comparison['groups']), PRIMARY_GROUPS)
        for gid in PRIMARY_GROUPS:
            g = self.comparison['groups'][gid]
            self.assertEqual(g['n'], len(g['cities']))
            for year in YEARS:
                cell = g['years'][str(year)]
                self.assertTrue(cell['complete'], msg=f'{gid} {year}')
                self.assertIsNotNone(cell['turnout_pct'])
                self.assertGreater(cell['eligible'], 0)
                self.assertGreaterEqual(cell['voters'], 0)
                self.assertNotIn(None, cell['missing_cities'])

    def test_2022_matches_embedded_voters_eligible(self):
        for gid in PRIMARY_GROUPS:
            cities = [
                r for r in self.rows
                if r.get('active') and r.get('group') == gid
            ]
            elig = sum(r['eligible2022'] for r in cities)
            voters = sum(r['voters2022'] for r in cities)
            expected = 100 * voters / elig
            got = self.comparison['groups'][gid]['years']['2022']['turnout_pct']
            self.assertAlmostEqual(got, expected, places=6)

    def test_delta_is_2022_minus_2021(self):
        for gid in PRIMARY_GROUPS:
            g = self.comparison['groups'][gid]
            self.assertAlmostEqual(
                g['delta_2021_to_2022_pp'],
                g['years']['2022']['turnout_pct'] - g['years']['2021']['turnout_pct'],
                places=9,
            )

    def test_missing_not_zeroed(self):
        rows = [dict(r) for r in self.rows]
        arab = next(r for r in rows if r.get('active') and r.get('group') == 'arab')
        arab['eligible2021'] = None
        bad = build_historical_comparison(rows)
        cell = bad['groups']['arab']['years']['2021']
        self.assertFalse(cell['complete'])
        self.assertIsNone(cell['turnout_pct'])
        self.assertTrue(cell['missing_cities'])

    def test_insights_capped(self):
        insights = build_insights(self.comparison, limit=3)
        self.assertLessEqual(len(insights), 3)
        self.assertTrue(insights)


if __name__ == '__main__':
    unittest.main()
