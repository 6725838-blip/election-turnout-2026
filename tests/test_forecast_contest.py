import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import forecast_contest as fc  # noqa: E402


def sample_payload(name='בדיקה'):
    parties = []
    remaining = 120
    for index, party in enumerate(fc.PARTIES):
        if index == len(fc.PARTIES) - 1:
            seats = remaining
        elif index < 3:
            seats = 30
            remaining -= 30
        else:
            seats = 0
        parties.append({'id': party['id'], 'name': party['name'], 'bloc': party['bloc'], 'seats': seats})
    return {
        'participant': name,
        'method': 'בדיקה',
        'parties': parties,
        'blocs': {'right': 60, 'center': 50, 'arab': 10},
        'version': 'test',
    }


class ForecastContestTests(unittest.TestCase):
    def test_validate_ok(self):
        result = fc.validate_payload(sample_payload())
        self.assertTrue(result['ok'])
        self.assertEqual(sum(result['parties'].values()), 120)
        self.assertEqual(sum(result['blocs'].values()), 120)

    def test_validate_rejects_bad_total(self):
        payload = sample_payload()
        payload['parties'][0]['seats'] = 4
        result = fc.validate_payload(payload)
        self.assertFalse(result['ok'])

    def test_save_and_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            submissions = tmp_path / 'submissions'
            truth = tmp_path / 'truth.json'
            public = tmp_path / 'public.json'
            with mock.patch.object(fc, 'SUBMISSIONS_DIR', submissions), \
                 mock.patch.object(fc, 'TRUTH_PATH', truth), \
                 mock.patch.object(fc, 'PUBLIC_PATH', public):
                validated = fc.validate_payload(sample_payload('אלפא'))
                self.assertTrue(validated['ok'])
                fc.save_submission(validated, timestamp='2026-10-26T12:00:00Z')
                snap = fc.write_public_snapshot()
                self.assertEqual(snap['count'], 1)
                self.assertEqual(snap['forecasts'][0]['participant'], 'אלפא')
                self.assertIsNotNone(snap['consensus'])
                data = json.loads(public.read_text(encoding='utf-8'))
                self.assertEqual(data['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
