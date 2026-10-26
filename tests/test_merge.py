import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from merge_live import merge_snapshot

def feed(time,records,national=None):
    return dict(format_version=1,source='Unit fixture',updated_at=f'2026-10-27T{time}:00+02:00',records=records,national_turnout_pct=national)

class MergeTests(unittest.TestCase):
    def setUp(self):
        self.old=feed('12:00',[dict(city='אלעד',eligible=100,voted=40)],30)

    def test_missing_retained_with_time(self):
        result=merge_snapshot(self.old,feed('13:00',[]))
        self.assertEqual(result['records'][0]['voted'],40)
        self.assertEqual(result['records'][0]['as_of'],self.old['updated_at'])
        self.assertTrue(result['records'][0]['preserved_previous'])
        self.assertEqual(result['national_turnout_pct'],30)
        self.assertTrue(result['national_preserved_previous'])

    def test_partial_does_not_replace_full(self):
        result=merge_snapshot(self.old,feed('13:00',[dict(city='אלעד',eligible=100,voted=20,partial=True)]))
        self.assertEqual(result['records'][0]['voted'],40)

    def test_partial_does_not_replace_preserved_full(self):
        mid=merge_snapshot(self.old,feed('13:00',[]))
        self.assertTrue(mid['records'][0]['preserved_previous'])
        result=merge_snapshot(mid,feed('14:00',[dict(city='אלעד',eligible=100,voted=10,partial=True)]))
        self.assertEqual(result['records'][0]['voted'],40)
        self.assertTrue(result['records'][0]['preserved_previous'])

    def test_older_row_in_newer_snapshot(self):
        result=merge_snapshot(self.old,feed('13:00',[dict(city='אלעד',turnout_pct=20,as_of='2026-10-27T11:00:00+02:00')]))
        self.assertEqual(result['records'][0]['voted'],40)

    def test_new_complete_report_replaces(self):
        result=merge_snapshot(self.old,feed('13:00',[dict(city='אלעד',eligible=100,voted=60)],50))
        self.assertEqual(result['records'][0]['voted'],60)
        self.assertNotIn('preserved_previous',result['records'][0])

    def test_older_snapshot_rejected(self):
        with self.assertRaises(ValueError): merge_snapshot(self.old,feed('11:00',[]))
