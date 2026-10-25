"""Validate normalized snapshots without inventing turnout data."""
import datetime as dt
import json
import math
import sys
from pathlib import Path

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('A source timestamp with timezone is required')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps must include timezone')
    return parsed

def number(value, name, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'Invalid {name}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} exceeds {maximum}')
    return value

def validate(feed):
    if not isinstance(feed, dict) or feed.get('format_version') != 1 or not isinstance(feed.get('records'), list):
        raise ValueError('Expected format_version 1 and records array')
    source = feed.get('source')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('Source description required')
    if feed.get('demo') or any(word in source.lower() for word in ('הדגמה','סימולציה','demo','simulation','test only')):
        raise ValueError('Demo data must not be published as a live snapshot')
    national = feed.get('national_turnout_pct')
    if national is not None:
        number(national, 'national_turnout_pct', 100)
        if feed.get('national_as_of'):
            timestamp(feed['national_as_of'])
    if feed['records'] or national is not None or feed.get('updated_at') is not None:
        timestamp(feed.get('updated_at'))
    seen = set()
    for row in feed['records']:
        if not isinstance(row, dict) or not isinstance(row.get('city'), str) or not row['city'].strip():
            raise ValueError('Each row requires city')
        import re
        import unicodedata
        city = re.sub(r'''[\s״׳'"־–-]''', '', unicodedata.normalize('NFKC', row['city'])).lower()
        if city in seen:
            raise ValueError('Duplicate city: ' + city)
        seen.add(city)
        e, v, p = row.get('eligible'), row.get('voted'), row.get('turnout_pct')
        if e is not None or v is not None:
            number(e, 'eligible')
            number(v, 'voted', e)
            if e <= 0:
                raise ValueError('eligible must be positive')
        if p is not None:
            number(p, 'turnout_pct', 100)
            if e is not None and abs(100*v/e - p) > 0.1:
                raise ValueError('turnout_pct disagrees with voted/eligible')
        elif e is None:
            raise ValueError('Turnout percentage or counts required')
        if 'partial' in row and not isinstance(row['partial'], bool):
            raise ValueError('partial must be boolean')
        if row.get('reported_stations') is not None or row.get('total_stations') is not None:
            total = number(row.get('total_stations'), 'total_stations')
            number(row.get('reported_stations'), 'reported_stations', total)
        timestamp(row.get('as_of') or feed.get('updated_at'))
    return feed

if __name__ == '__main__':
    validate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')))
    print('Live snapshot valid')
