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
            'id': 1,
            'groupItemTitle': 'Gadi Eizenkot',
            'slug': 'will-gadi-eizenkot-be-the-next-prime-minister-of-israel',
            'outcomes': '["Yes", "No"]',
            'outcomePrices': '["0.56", "0.44"]',
            'clobTokenIds': '["111", "222"]',
            'volume': 100,
            'image': 'https://example.com/gadi.jpg',
        },
        {
            'id': 2,
            'groupItemTitle': 'Benjamin Netanyahu',
            'slug': 'will-benjamin-netanyahu-be-the-next-prime-minister-of-israel',
            'outcomes': ['Yes', 'No'],
            'outcomePrices': ['0.26', '0.74'],
            'clobTokenIds': ['333', '444'],
            'volume': 200,
        },
        {
            'id': 3,
            'groupItemTitle': 'Naftali Bennett',
            'outcomes': ['Yes', 'No'],
            'outcomePrices': ['0.11', '0.89'],
            'clobTokenIds': ['555', '666'],
            'volume': 50,
        },
        {
            'id': 99,
            'groupItemTitle': 'Tiny Candidate',
            'outcomes': ['Yes', 'No'],
            'outcomePrices': ['0.001', '0.999'],
            'clobTokenIds': ['777', '888'],
            'volume': 10,
        },
    ],
}


class PolymarketSnapshotTests(unittest.TestCase):
    def test_only_tracked_three_in_fixed_order(self):
        hist = {'111': [{'t': 1, 'p': 0.5}]}
        snap = pm.build_snapshot(SAMPLE_EVENT, hist)
        self.assertEqual(snap['format_version'], 3)
        self.assertEqual(snap['delivery'], 'same-origin-snapshot')
        self.assertEqual(snap['poll_seconds'], 60)
        self.assertEqual(snap['histories'], hist)
        names = [c['name'] for c in snap['candidates']]
        self.assertEqual(names, ['Gadi Eizenkot', 'Benjamin Netanyahu', 'Naftali Bennett'])
        self.assertEqual(snap['candidates'][0]['name_he'], 'גדי איזנקוט')
        self.assertEqual(snap['candidates'][0]['yes_token'], '111')
        self.assertEqual(snap['candidates'][0]['pct'], 56.0)
        self.assertNotIn('Tiny Candidate', names)

    def test_yes_prob_from_last_trade(self):
        m = {'lastTradePrice': 0.33, 'outcomes': ['Yes', 'No'], 'outcomePrices': None}
        self.assertAlmostEqual(pm._yes_prob(m), 0.33)


if __name__ == '__main__':
    unittest.main()
