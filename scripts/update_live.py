#!/usr/bin/env python3
"""Fetch ONLY an explicitly verified official feed. Disabled by default.

Supports OFFICIAL_FEED_FORMAT:
  live             — body already matches live-turnout schema (default)
  govmap_municipal — GovMap municipal_data.json adapted via adapt_govmap
"""
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from validate_live import validate, timestamp
from merge_live import merge_snapshot

DEST = Path(__file__).resolve().parents[1] / 'live-turnout.json'
MAX_BYTES_LIVE = 2_000_000
MAX_BYTES_GOVMAP = 3_000_000


def _fetch(url: str, max_bytes: int) -> bytes:
    parts = urllib.parse.urlparse(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('A verified HTTPS URL without embedded credentials is required')
    request = urllib.request.Request(
        url,
        headers={'Accept': 'application/json', 'User-Agent': 'PublicTurnoutDashboard/1.0'},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200 or urllib.parse.urlparse(response.url).scheme != 'https':
            raise ValueError('Feed request failed or redirected to insecure HTTP')
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f'Feed exceeds {max_bytes} bytes')
    if raw.lstrip().startswith(b'<'):
        raise ValueError('Feed URL returned HTML instead of JSON')
    return raw


def main():
    if os.environ.get('OFFICIAL_FEED_VERIFIED') != 'true':
        print('Official feed disabled; existing data unchanged.')
        return
    url = os.environ.get('OFFICIAL_FEED_URL', '').strip()
    election_date = os.environ.get('ELECTION_DATE', '').strip()
    feed_format = os.environ.get('OFFICIAL_FEED_FORMAT', 'live').strip().lower() or 'live'
    if not election_date:
        raise ValueError('Set ELECTION_DATE only after verifying the election date')

    if feed_format == 'govmap_municipal':
        from adapt_govmap import load_codes, to_live_feed

        raw = _fetch(url, MAX_BYTES_GOVMAP)
        municipal = json.loads(raw.decode('utf-8-sig'))
        feed = to_live_feed(municipal, load_codes())
    elif feed_format == 'live':
        raw = _fetch(url, MAX_BYTES_LIVE)
        feed = json.loads(raw.decode('utf-8-sig'))
    else:
        raise ValueError(f'Unsupported OFFICIAL_FEED_FORMAT: {feed_format}')

    feed = validate(feed)
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
    temporary.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(DEST)
    print(f'Updated {len(feed["records"])} reports; deploy this snapshot in the same workflow.')


if __name__ == '__main__':
    main()
