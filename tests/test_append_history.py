import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from append_history import append_history, fingerprint, snapshot_point  # noqa: E402


FEED = {
    'format_version': 1,
    'source': 'Unit test',
    'updated_at': '2026-10-27T12:00:00+02:00',
    'national_turnout_pct': 40.0,
    'records': [
        {'city': 'אלעד', 'eligible': 100, 'voted': 40, 'turnout_pct': 40.0, 'partial': False, 'as_of': '2026-10-27T12:00:00+02:00'},
    ],
}


class AppendHistoryTests(unittest.TestCase):
    def test_fingerprint_stable(self):
        self.assertEqual(fingerprint(FEED), fingerprint(json.loads(json.dumps(FEED))))

    def test_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'history.json'
            self.assertTrue(append_history(FEED, path))
            self.assertFalse(append_history(FEED, path))
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(data['points']), 1)
            cities = data['points'][0]['cities']
            self.assertTrue(any(v.get('city') == 'אלעד' for v in cities.values()))

    def test_new_point_when_votes_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'history.json'
            append_history(FEED, path)
            nxt = json.loads(json.dumps(FEED))
            nxt['updated_at'] = '2026-10-27T14:00:00+02:00'
            nxt['records'][0]['voted'] = 55
            nxt['records'][0]['turnout_pct'] = 55.0
            nxt['records'][0]['as_of'] = '2026-10-27T14:00:00+02:00'
            self.assertTrue(append_history(nxt, path))
            self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['points']), 2)

    def test_snapshot_requires_timestamp(self):
        self.assertIsNone(snapshot_point({'records': [], 'national_turnout_pct': None}))


if __name__ == '__main__':
    unittest.main()
