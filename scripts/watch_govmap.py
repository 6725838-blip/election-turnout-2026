#!/usr/bin/env python3
"""Report whether GovMap Knesset-26 municipal turnout JSON is available."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

CATALOG_URL = 'https://elections.govmap.gov.il/data/votes/elections.json'
MUNICIPAL_TMPL = 'https://elections.govmap.gov.il/data/votes/{path}/municipal_data.json'


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'PublicTurnoutDashboard/1.0', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read()
        if raw.lstrip().startswith(b'<'):
            raise ValueError('HTML response')
        return json.loads(raw.decode('utf-8-sig'))


def municipal_ready(url: str) -> bool:
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'PublicTurnoutDashboard/1.0', 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            if response.status != 200:
                return False
            raw = response.read(2048)
            ctype = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            if raw.lstrip().startswith(b'<'):
                return False
            return 'json' in ctype or raw.lstrip().startswith(b'{')
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return False


def check(knesset: str = '26') -> dict:
    result = {
        'knesset': knesset,
        'catalog_has_election': False,
        'municipal_url': MUNICIPAL_TMPL.format(path=knesset),
        'municipal_ready': False,
        'ready': False,
    }
    path = knesset
    try:
        catalog = fetch_json(CATALOG_URL)
        elections = catalog.get('elections') or {}
        if knesset in elections:
            result['catalog_has_election'] = True
            path = elections[knesset].get('path') or knesset
        result['municipal_url'] = MUNICIPAL_TMPL.format(path=path)
    except Exception as exc:
        result['catalog_error'] = str(exc)

    result['municipal_ready'] = municipal_ready(result['municipal_url'])
    result['ready'] = bool(result['municipal_ready'] and (result['catalog_has_election'] or result['municipal_ready']))
    # Prefer requiring municipal JSON; catalog alone is not enough
    result['ready'] = bool(result['municipal_ready'])
    if result['municipal_ready'] and not result['catalog_has_election']:
        result['note'] = 'municipal JSON present without catalog entry'
    return result


def write_github_output(ready: bool):
    path = os.environ.get('GITHUB_OUTPUT')
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(f'ready={"true" if ready else "false"}\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--knesset', default='26')
    args = parser.parse_args(argv)
    result = check(args.knesset)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    write_github_output(result['ready'])
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write('## GovMap watch\n')
            handle.write(f"- ready: `{result['ready']}`\n")
            handle.write(f"- catalog has {args.knesset}: `{result['catalog_has_election']}`\n")
            handle.write(f"- municipal: `{result['municipal_url']}` → `{result['municipal_ready']}`\n")
    return 0 if result['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
