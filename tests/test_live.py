import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_live import validate
import update_live

class SnapshotTests(unittest.TestCase):
    def fixture(self):
        # Synthetic validation fixture; never written to the public snapshot.
        return dict(format_version=1, source='Validation fixture', updated_at='2026-10-27T12:00:00+02:00',
                    national_turnout_pct=50, records=[dict(city='Fixture city', eligible=100, voted=50, turnout_pct=50)])

    def test_empty_snapshot(self):
        validate(dict(format_version=1, source='Not connected', updated_at=None, national_turnout_pct=None, records=[]))

    def test_invalid_values_rejected(self):
        for value in (True, float('nan'), float('inf'), -1, 101, '50'):
            feed=self.fixture()
            feed['national_turnout_pct']=value
            with self.subTest(value=value), self.assertRaises(ValueError): validate(feed)

    def test_inconsistent_counts_rejected(self):
        feed=self.fixture()
        feed['records'][0]['voted']=75
        with self.assertRaises(ValueError): validate(feed)

    def test_demo_and_missing_timezone_rejected(self):
        feed=self.fixture()
        feed['source']='demo'
        with self.assertRaises(ValueError): validate(feed)
        feed=self.fixture()
        feed['updated_at']='2026-10-27T12:00:00'
        with self.assertRaises(ValueError): validate(feed)

    def test_disabled_updater_makes_no_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(update_live.urllib.request, 'urlopen') as request:
            update_live.main()
            request.assert_not_called()

    def test_older_feed_does_not_overwrite(self):
        feed=self.fixture()
        previous=copy.deepcopy(feed)
        previous['updated_at']='2026-10-27T13:00:00+02:00'
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'live-turnout.json'
            dest.write_text(json.dumps(previous))
            with patch.object(update_live, 'DEST', dest), patch.dict(os.environ, {
                'OFFICIAL_FEED_VERIFIED':'true', 'OFFICIAL_FEED_URL':'https://example.invalid/fixture', 'ELECTION_DATE':'2026-10-27'
            }), patch.object(update_live.urllib.request, 'urlopen') as request:
                response=request.return_value.__enter__.return_value
                response.status=200
                response.url='https://example.invalid/fixture'
                response.read.return_value=json.dumps(feed).encode()
                with self.assertRaises(ValueError): update_live.main()
                self.assertEqual(json.loads(dest.read_text()), previous)

if __name__ == '__main__': unittest.main()
