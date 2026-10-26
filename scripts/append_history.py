#!/usr/bin/env python3
"""Append a deduplicated city-level snapshot to turnout-history.json."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from city_norm import city_key
from validate_live import timestamp

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'turnout-history.json'
MAX_POINTS = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def fingerprint(feed: dict) -> str:
    cities = []
    for row in sorted(feed.get('records') or [], key=lambda r: city_key(r.get('city', ''))):
        cities.append({
            'city': city_key(row.get('city', '')),
            'eligible': row.get('eligible'),
            'voted': row.get('voted'),
            'turnout_pct': row.get('turnout_pct'),
            'partial': bool(row.get('partial')),
            'as_of': row.get('as_of') or feed.get('updated_at'),
            'preserved_previous': bool(row.get('preserved_previous')),
        })
    payload = {
        'as_of': feed.get('updated_at'),
        'national_turnout_pct': feed.get('national_turnout_pct'),
        'national_as_of': feed.get('national_as_of'),
        'cities': cities,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def snapshot_point(feed: dict, recorded_at: str | None = None) -> dict | None:
    if not feed or not feed.get('updated_at'):
        return None
    if not feed.get('records') and feed.get('national_turnout_pct') is None:
        return None
    cities = {}
    for row in feed.get('records') or []:
        name = row.get('city')
        if not name:
            continue
        cities[city_key(name)] = {
            'city': name,
            'eligible': row.get('eligible'),
            'voted': row.get('voted'),
            'turnout_pct': row.get('turnout_pct'),
            'partial': bool(row.get('partial') or False),
            'as_of': row.get('as_of') or feed.get('updated_at'),
            'preserved_previous': bool(row.get('preserved_previous') or False),
            'reported_stations': row.get('reported_stations'),
            'total_stations': row.get('total_stations'),
        }
    return {
        'as_of': feed['updated_at'],
        'recorded_at': recorded_at or _now_iso(),
        'source': feed.get('source') or '',
        'national_turnout_pct': feed.get('national_turnout_pct'),
        'national_as_of': feed.get('national_as_of') or feed.get('updated_at'),
        'national_preserved_previous': bool(feed.get('national_preserved_previous') or False),
        'cities': cities,
        'fingerprint': fingerprint(feed),
    }


def load_history(path: Path = HISTORY) -> dict:
    if not path.exists():
        return {'format_version': 1, 'points': []}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        return {'format_version': 1, 'points': []}
    points = data.get('points')
    if not isinstance(points, list):
        points = []
    return {'format_version': 1, 'points': points}


def append_history(feed: dict, path: Path = HISTORY) -> bool:
    """Return True if a new point was written."""
    point = snapshot_point(feed)
    if point is None:
        return False
    history = load_history(path)
    points = history['points']
    if points and points[-1].get('fingerprint') == point['fingerprint']:
        return False
    # Also skip if same feed updated_at and identical city set fingerprints already present.
    for prev in reversed(points[-5:]):
        if prev.get('fingerprint') == point['fingerprint']:
            return False
    points.append(point)
    if len(points) > MAX_POINTS:
        points[:] = points[-MAX_POINTS:]
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps({'format_version': 1, 'points': points}, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    temporary.replace(path)
    return True


def main():
    live = ROOT / 'live-turnout.json'
    if not live.exists():
        print('No live-turnout.json; history unchanged.')
        return
    feed = json.loads(live.read_text(encoding='utf-8-sig'))
    if append_history(feed):
        print(f'Appended history point as_of={feed.get("updated_at")}')
    else:
        print('History unchanged (empty, incomplete, or duplicate snapshot).')


if __name__ == '__main__':
    main()
