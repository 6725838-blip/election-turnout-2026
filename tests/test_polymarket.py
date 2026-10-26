import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update_polymarket as pm  # noqa: E402


SAMPLE_EVENT = {
    'title': 'Prime Minister of Israel after the next election?',
    'slug': 'who-will-be-the-next-prime-minister-of-israel-after-the-next-election',
    'volume': 1000.5,
    'endDate': '2026-10-27T00:00:00Z',
    'markets': [
        {
            'groupItemTitle': 'Gadi Eizenkot',
            'outcomes': '["Yes", "No"]',
            'outcomePrices': '["0.56", "0.44"]',
            'volume': 100,
            'image': 'https://example.com/gadi.jpg',
        },
        {
            'groupItemTitle': 'Benjamin Netanyahu',
            'outcomes': ['Yes', 'No'],
            'outcomePrices': ['0.26', '0.74'],
            'volume': 200,
            'lastTradePrice': 0.27,
        },
        {
            'groupItemTitle': 'Tiny Candidate',
            'outcomes': ['Yes', 'No'],
            'outcomePrices': ['0.001', '0.999'],
            'volume': 10,
        },
    ],
}


class PolymarketSnapshotTests(unittest.TestCase):
    def test_build_snapshot_sorts_and_he_names(self):
        snap = pm.build_snapshot(SAMPLE_EVENT)
        self.assertEqual(snap['format_version'], 1)
        self.assertEqual(snap['source'], 'Polymarket')
        self.assertEqual(snap['candidates'][0]['name'], 'Gadi Eizenkot')
        self.assertEqual(snap['candidates'][0]['name_he'], 'גדי איזנקוט')
        self.assertEqual(snap['candidates'][0]['pct'], 56.0)
        self.assertEqual(snap['candidates'][1]['name_he'], 'בנימין נתניהו')
        self.assertIn('polymarket.com/event/', snap['url'])

    def test_yes_prob_from_last_trade(self):
        m = {'lastTradePrice': 0.33, 'outcomes': ['Yes', 'No'], 'outcomePrices': None}
        self.assertAlmostEqual(pm._yes_prob(m), 0.33)


if __name__ == '__main__':
    unittest.main()
