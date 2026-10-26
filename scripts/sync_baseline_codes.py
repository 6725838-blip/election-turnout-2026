#!/usr/bin/env python3
"""Fill municipal codes and verify 2022 baselines against GovMap Knesset-25 data."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from city_norm import city_key

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
CODES_PATH = Path(__file__).resolve().parent / 'city_codes.json'
GOVMAP_25 = 'https://elections.govmap.gov.il/data/votes/25/municipal_data.json'
BASELINE_RE = re.compile(
    r'(<script id="baseline-data" type="application/json">)(.*?)(</script>)',
    re.S,
)


def fetch_govmap(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'PublicTurnoutDashboard/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        ctype = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if ctype and ctype != 'application/json' and not raw.lstrip().startswith(b'{'):
            raise ValueError(f'Expected JSON from {url}, got {ctype}')
        return json.loads(raw.decode('utf-8-sig'))


def load_baseline(html: str) -> list:
    match = BASELINE_RE.search(html)
    if not match:
        raise ValueError('baseline-data script not found in index.html')
    return json.loads(match.group(2))


def govmap_index(data: dict) -> dict[str, dict]:
    """Map normalized Hebrew name -> {code, name, eligible, voted, turnout}."""
    out = {}
    features = data.get('features') or {}
    for code, feat in features.items():
        name = feat.get('שם ישוב')
        if not name:
            continue
        eligible = feat.get('בזב')
        voted = feat.get('מצביעים')
        turnout = None
        if isinstance(eligible, (int, float)) and eligible > 0 and isinstance(voted, (int, float)):
            turnout = round(100.0 * voted / eligible, 2)
        entry = {
            'code': int(code) if str(code).isdigit() else code,
            'name': name,
            'eligible': eligible,
            'voted': voted,
            'turnout': turnout,
        }
        out[city_key(name)] = entry
    return out


# Manual aliases when baseline spelling differs from GovMap "שם ישוב"
ALIASES = {
    city_key('תל אביב-יפו'): city_key('תל אביב  יפו'),
    city_key('תל אביב יפו'): city_key('תל אביב  יפו'),
}


def resolve(name: str, index: dict) -> dict | None:
    key = city_key(name)
    if key in index:
        return index[key]
    alt = ALIASES.get(key)
    if alt and alt in index:
        return index[alt]
    # fuzzy: try without double spaces already handled by city_key
    for gkey, entry in index.items():
        if key in gkey or gkey in key:
            if abs(len(key) - len(gkey)) <= 3:
                return entry
    return None


def sync(rows: list, index: dict, update_stats: bool) -> tuple[list, list]:
    report = []
    for row in rows:
        hit = resolve(row['name'], index)
        if not hit:
            report.append(f"MISS  {row['name']}: no GovMap match")
            continue
        old_code = row.get('code')
        new_code = hit['code']
        if old_code != new_code:
            report.append(f"CODE  {row['name']}: {old_code} -> {new_code}")
            row['code'] = new_code
        if update_stats and hit['eligible'] is not None and hit['voted'] is not None:
            elig, voted, turnout = hit['eligible'], hit['voted'], hit['turnout']
            if row.get('eligible2022') != elig:
                report.append(f"ELIG  {row['name']}: {row.get('eligible2022')} -> {elig}")
                row['eligible2022'] = elig
            if row.get('voters2022') != voted:
                report.append(f"VOTE  {row['name']}: {row.get('voters2022')} -> {voted}")
                row['voters2022'] = voted
            if turnout is not None and abs(float(row.get('p2022') or 0) - turnout) > 0.05:
                report.append(f"P2022 {row['name']}: {row.get('p2022')} -> {turnout}")
                row['p2022'] = turnout
        elif hit['turnout'] is not None and row.get('p2022') is not None:
            if abs(float(row['p2022']) - hit['turnout']) > 0.15:
                report.append(
                    f"WARN  {row['name']}: p2022={row['p2022']} govmap={hit['turnout']} (not auto-updated)"
                )
    return rows, report


def write_codes(rows: list) -> dict:
    by_code = {}
    by_name = {}
    active_names = []
    for row in rows:
        code = row.get('code')
        if code is None:
            continue
        by_code[str(code)] = row['name']
        by_name[row['name']] = code
        if row.get('active'):
            active_names.append(row['name'])
    payload = {
        'format_version': 1,
        'source': 'Synced from GovMap municipal_data Knesset 25 + index.html baseline',
        'by_code': by_code,
        'by_name': by_name,
        'active_names': active_names,
    }
    CODES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return payload


def write_index(html: str, rows: list) -> str:
    body = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
    updated, n = BASELINE_RE.subn(r'\1' + body + r'\3', html, count=1)
    if n != 1:
        raise ValueError('Failed to rewrite baseline-data in index.html')
    return updated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=GOVMAP_25, help='GovMap municipal_data URL')
    parser.add_argument('--update-stats', action='store_true', help='Overwrite eligible2022/voters2022/p2022 from GovMap')
    parser.add_argument('--dry-run', action='store_true', help='Report only; do not write files')
    parser.add_argument('--fixture', type=Path, help='Local municipal_data JSON instead of URL')
    args = parser.parse_args(argv)

    data = json.loads(args.fixture.read_text(encoding='utf-8-sig')) if args.fixture else fetch_govmap(args.url)
    index = govmap_index(data)
    html = INDEX.read_text(encoding='utf-8')
    rows = load_baseline(html)
    rows, report = sync(rows, index, update_stats=args.update_stats)
    missing = [r['name'] for r in rows if r.get('code') is None]
    print(f'GovMap features: {len(index)}; baseline rows: {len(rows)}; still missing codes: {len(missing)}')
    for line in report:
        print(line)
    if missing:
        print('MISSING CODES:', ', '.join(missing))
    if args.dry_run:
        print('Dry run — files not written.')
        return 0 if not missing else 1
    write_codes(rows)
    INDEX.write_text(write_index(html, rows), encoding='utf-8')
    print(f'Wrote {CODES_PATH.relative_to(ROOT)} and updated baseline-data in index.html')
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
