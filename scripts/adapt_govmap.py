#!/usr/bin/env python3
"""Convert GovMap municipal_data.json into live-turnout format_version 1."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from city_norm import city_key

CODES_PATH = Path(__file__).resolve().parent / 'city_codes.json'
GOVMAP_25 = 'https://elections.govmap.gov.il/data/votes/25/municipal_data.json'
DEFAULT_SOURCE = 'GovMap elections municipal_data (ועדת הבחירות / מפ״י)'


def load_codes(path: Path | None = None) -> dict:
    path = path or CODES_PATH
    return json.loads(path.read_text(encoding='utf-8-sig'))


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'PublicTurnoutDashboard/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('GovMap body exceeds 3 MB')
        ctype = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if raw.lstrip().startswith(b'<'):
            raise ValueError(f'GovMap URL returned HTML, not JSON: {url}')
        if ctype and 'json' not in ctype and not raw.lstrip().startswith(b'{'):
            raise ValueError(f'Unexpected content-type {ctype} for {url}')
        return json.loads(raw.decode('utf-8-sig'))


def _wanted_names(codes: dict, active_only: bool) -> set[str]:
    if active_only and codes.get('active_names'):
        return set(codes['active_names'])
    return set(codes.get('by_name') or {})


def _name_by_code(codes: dict) -> dict[str, str]:
    return {str(k): v for k, v in (codes.get('by_code') or {}).items()}


def _name_index(codes: dict) -> dict[str, str]:
    """normalized name -> canonical baseline name"""
    out = {}
    for name in codes.get('by_name') or {}:
        out[city_key(name)] = name
    return out


def to_live_feed(
    municipal: dict,
    codes: dict,
    *,
    source: str | None = None,
    active_only: bool = True,
    updated_at_override: str | None = None,
) -> dict:
    if not isinstance(municipal, dict) or not isinstance(municipal.get('features'), dict):
        raise ValueError('Expected GovMap municipal_data with features object')
    features = municipal['features']
    totals = municipal.get('totals') or {}
    kalpi = totals.get('kalpi')
    counted = totals.get('kalpi_counted')
    nationwide_partial = (
        isinstance(kalpi, (int, float))
        and isinstance(counted, (int, float))
        and counted < kalpi
    )
    by_code = _name_by_code(codes)
    by_norm = _name_index(codes)
    wanted = _wanted_names(codes, active_only)
    generated = updated_at_override or municipal.get('generated')
    if not isinstance(generated, str) or not generated.strip():
        raise ValueError('GovMap municipal_data requires generated timestamp')

    records = []
    unmatched = []
    for code, feat in features.items():
        if not isinstance(feat, dict):
            continue
        baseline_name = by_code.get(str(code))
        if not baseline_name:
            gov_name = feat.get('שם ישוב')
            baseline_name = by_norm.get(city_key(gov_name)) if gov_name else None
        if not baseline_name:
            continue
        if wanted and baseline_name not in wanted:
            continue
        eligible = feat.get('בזב')
        voted = feat.get('מצביעים')
        if not isinstance(eligible, (int, float)) or not isinstance(voted, (int, float)):
            unmatched.append(f'{baseline_name} ({code}): missing בזב/מצביעים')
            continue
        if eligible <= 0 or voted < 0 or voted > eligible:
            unmatched.append(f'{baseline_name} ({code}): invalid counts')
            continue
        turnout = round(100.0 * voted / eligible, 2)
        row = {
            'city': baseline_name,
            'eligible': int(eligible) if float(eligible).is_integer() else float(eligible),
            'voted': int(voted) if float(voted).is_integer() else float(voted),
            'turnout_pct': turnout,
            'as_of': generated,
        }
        if nationwide_partial:
            row['partial'] = True
            if isinstance(counted, (int, float)) and isinstance(kalpi, (int, float)):
                row['reported_stations'] = int(counted)
                row['total_stations'] = int(kalpi)
        else:
            row['partial'] = False
        records.append(row)

    # Stable order by baseline name
    records.sort(key=lambda r: r['city'])
    for warning in unmatched:
        print('WARN', warning, file=sys.stderr)

    missing = sorted(wanted - {r['city'] for r in records}) if wanted else []
    # Only warn on gaps for full municipal dumps (unit fixtures are tiny).
    if missing and len(features) >= max(100, len(wanted)):
        for name in missing:
            print(f'WARN missing baseline city in feed: {name}', file=sys.stderr)

    # totals lacks eligible/voters; leave national for manual/official bulletin
    feed = {
        'format_version': 1,
        'source': source or os.environ.get('OFFICIAL_FEED_SOURCE', DEFAULT_SOURCE),
        'updated_at': generated,
        'national_turnout_pct': None,
        'records': records,
    }
    return feed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='GovMap municipal_data URL')
    parser.add_argument('--fixture-from-25', action='store_true', help='Fetch Knesset-25 municipal_data')
    parser.add_argument('--input', type=Path, help='Local municipal_data JSON')
    parser.add_argument('--codes', type=Path, default=CODES_PATH)
    parser.add_argument('--out', type=Path, help='Write live-turnout JSON')
    parser.add_argument('--all-cities', action='store_true', help='Include inactive baseline cities')
    parser.add_argument('--updated-at', help='Override updated_at (ISO with timezone)')
    parser.add_argument('--source', help='Override source string')
    args = parser.parse_args(argv)

    if args.input:
        municipal = json.loads(args.input.read_text(encoding='utf-8-sig'))
    else:
        url = args.url or (GOVMAP_25 if args.fixture_from_25 else None)
        if not url:
            raise SystemExit('Provide --url, --input, or --fixture-from-25')
        municipal = fetch_json(url)

    codes = load_codes(args.codes)
    feed = to_live_feed(
        municipal,
        codes,
        source=args.source,
        active_only=not args.all_cities,
        updated_at_override=args.updated_at,
    )
    text = json.dumps(feed, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.write_text(text, encoding='utf-8')
        print(f'Wrote {args.out} with {len(feed["records"])} records')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
