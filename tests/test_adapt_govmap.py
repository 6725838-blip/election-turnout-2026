import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from adapt_govmap import to_live_feed, load_codes
from validate_live import validate


class AdaptGovmapTests(unittest.TestCase):
    def setUp(self):
        self.codes = load_codes()
        # Minimal municipal fixture with known baseline cities
        self.municipal = {
            'version': 2,
            'generated': '2026-10-27T12:00:00+02:00',
            'layer': 'municipal',
            'totals': {'kalpi': 100, 'kalpi_counted': 100, 'votes_counted': 1},
            'features': {
                '6100': {'שם ישוב': 'בני ברק', 'בזב': 1000, 'מצביעים': 500},
                '1309': {'שם ישוב': 'אלעד', 'בזב': 2000, 'מצביעים': 800},
                '9999': {'שם ישוב': 'לא במפה', 'בזב': 10, 'מצביעים': 5},
            },
        }

    def test_maps_codes_to_baseline_names(self):
        feed = to_live_feed(self.municipal, self.codes)
        validate(feed)
        cities = {r['city'] for r in feed['records']}
        self.assertIn('בני ברק', cities)
        self.assertIn('אלעד', cities)
        self.assertNotIn('לא במפה', cities)
        self.assertEqual(feed['national_turnout_pct'], None)
        self.assertFalse(any(r.get('partial') for r in feed['records']))

    def test_partial_when_kalpi_incomplete(self):
        data = json.loads(json.dumps(self.municipal))
        data['totals']['kalpi_counted'] = 40
        feed = to_live_feed(data, self.codes)
        self.assertTrue(all(r.get('partial') for r in feed['records']))
        self.assertEqual(feed['records'][0]['reported_stations'], 40)
        self.assertEqual(feed['records'][0]['total_stations'], 100)

    def test_active_only_filters(self):
        # בית שאן is inactive in baseline
        data = json.loads(json.dumps(self.municipal))
        data['features']['9200'] = {'שם ישוב': 'בית שאן', 'בזב': 100, 'מצביעים': 50}
        feed = to_live_feed(data, self.codes, active_only=True)
        self.assertNotIn('בית שאן', {r['city'] for r in feed['records']})
        feed_all = to_live_feed(data, self.codes, active_only=False)
        self.assertIn('בית שאן', {r['city'] for r in feed_all['records']})


if __name__ == '__main__':
    unittest.main()
