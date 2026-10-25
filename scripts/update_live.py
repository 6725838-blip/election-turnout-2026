#!/usr/bin/env python3
"""Fetch ONLY an explicitly verified, normalized official feed. Disabled by default."""
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from validate_live import validate, timestamp
from merge_live import merge_snapshot

DEST = Path(__file__).resolve().parents[1] / 'live-turnout.json'

def main():
    if os.environ.get('OFFICIAL_FEED_VERIFIED') != 'true':
        print('Official feed disabled; existing data unchanged.')
        return
    url = os.environ.get('OFFICIAL_FEED_URL', '').strip()
    election_date = os.environ.get('ELECTION_DATE', '').strip()
    parts = urllib.parse.urlparse(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('A verified HTTPS URL without embedded credentials is required')
    if not election_date:
        raise ValueError('Set ELECTION_DATE only after verifying the election date')
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'PublicTurnoutDashboard/1.0'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200 or urllib.parse.urlparse(response.url).scheme != 'https':
            raise ValueError('Feed request failed or redirected to insecure HTTP')
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Feed exceeds 2 MB')
    feed = validate(json.loads(raw.decode('utf-8-sig')))
    if not feed['records'] and feed.get('national_turnout_pct') is None:
        print('No reports; retaining prior snapshot.')
        return
    updated = timestamp(feed['updated_at'])
    if updated.date().isoformat() != election_date:
        raise ValueError('Source timestamp does not match verified ELECTION_DATE')
    existing = json.loads(DEST.read_text(encoding='utf-8-sig')) if DEST.exists() else {}
    if existing.get('updated_at') and updated < timestamp(existing['updated_at']):
        raise ValueError('Refusing an older snapshot')
    feed = merge_snapshot(existing, feed)
    temporary = DEST.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(feed, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(DEST)
    print(f'Updated {len(feed["records"])} reports; deploy this snapshot in the same workflow.')

if __name__ == '__main__':
    main()
