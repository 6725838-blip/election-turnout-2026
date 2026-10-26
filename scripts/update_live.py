#!/usr/bin/env python3
"""Fetch ONLY an explicitly verified official feed. Disabled by default.

Supports OFFICIAL_FEED_FORMAT:
  live             — body already matches live-turnout schema (default)
  govmap_municipal — GovMap municipal_data.json adapted via adapt_govmap

If the verified URL is not publishing JSON yet (HTML SPA, 404, timeout),
exit quietly and keep the previous snapshot so scheduled runs stay green.
"""
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from validate_live import validate, timestamp
from merge_live import merge_snapshot

DEST = Path(__file__).resolve().parents[1] / 'live-turnout.json'
MAX_BYTES_LIVE = 2_000_000
MAX_BYTES_GOVMAP = 3_000_000


class FeedNotReady(Exception):
    """Remote feed is configured but not publishing usable JSON yet."""


def _fetch(url: str, max_bytes: int) -> bytes:
    parts = urllib.parse.urlparse(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('A verified HTTPS URL without embedded credentials is required')
    request = urllib.request.Request(
        url,
        headers={'Accept': 'application/json', 'User-Agent': 'PublicTurnoutDashboard/1.0'},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if urllib.parse.urlparse(response.url).scheme != 'https':
                raise ValueError('Feed request redirected to insecure HTTP')
            if response.status != 200:
                raise FeedNotReady(f'HTTP {response.status}')
            raw = response.read(max_bytes + 1)
    except FeedNotReady:
        raise
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 403, 502, 503, 504):
            raise FeedNotReady(f'HTTP {exc.code}') from exc
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedNotReady(str(exc)) from exc
    if len(raw) > max_bytes:
        raise ValueError(f'Feed exceeds {max_bytes} bytes')
    if raw.lstrip().startswith(b'<'):
        raise FeedNotReady('Feed URL returned HTML instead of JSON')
    if not raw.lstrip().startswith((b'{', b'[')):
        raise FeedNotReady('Feed body is not JSON')
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

    try:
        if feed_format == 'govmap_municipal':
            from adapt_govmap import load_codes, to_live_feed

            raw = _fetch(url, MAX_BYTES_GOVMAP)
            try:
                municipal = json.loads(raw.decode('utf-8-sig'))
            except json.JSONDecodeError as exc:
                raise FeedNotReady(f'Invalid JSON: {exc}') from exc
            if not isinstance(municipal.get('features'), dict) or not municipal.get('features'):
                raise FeedNotReady('GovMap municipal_data has no features yet')
            feed = to_live_feed(municipal, load_codes())
        elif feed_format == 'live':
            raw = _fetch(url, MAX_BYTES_LIVE)
            try:
                feed = json.loads(raw.decode('utf-8-sig'))
            except json.JSONDecodeError as exc:
                raise FeedNotReady(f'Invalid JSON: {exc}') from exc
        else:
            raise ValueError(f'Unsupported OFFICIAL_FEED_FORMAT: {feed_format}')
    except FeedNotReady as exc:
        print(f'Official feed not ready yet ({exc}); keeping previous snapshot.')
        return

    feed = validate(feed)
    if not feed['records'] and feed.get('national_turnout_pct') is None:
        print('No reports; retaining prior snapshot.')
        return
    updated = timestamp(feed['updated_at'])
    if updated.date().isoformat() != election_date:
        # Before election day a premature file with another date must not publish.
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
