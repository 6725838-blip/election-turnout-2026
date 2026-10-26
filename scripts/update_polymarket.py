#!/usr/bin/env python3
"""Fetch Polymarket Israel PM odds + week price history into a same-origin snapshot.

Browser clients under NetFree (and similar filters) cannot call polymarket.com
directly. CI / this script pulls Gamma + CLOB server-side and writes
polymarket-pm.json so GitHub Pages serves everything from one origin.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'polymarket-pm.json'
API = (
    'https://gamma-api.polymarket.com/events'
    '?slug=who-will-be-the-next-prime-minister-of-israel-after-the-next-election'
)
EVENT_URL = (
    'https://polymarket.com/event/'
    'who-will-be-the-next-prime-minister-of-israel-after-the-next-election'
)
CLOB = 'https://clob.polymarket.com/prices-history'
MAX_BYTES = 2_500_000
HISTORY_FIDELITY = 5  # densest week series; UI downsamples for coarser buttons
HISTORY_INTERVAL = '1w'

TRACKED = (
    {'name': 'Gadi Eizenkot', 'name_he': 'גדי איזנקוט', 'color': '#0d6b58'},
    {'name': 'Benjamin Netanyahu', 'name_he': 'בנימין נתניהו', 'color': '#b86a0a'},
    {'name': 'Naftali Bennett', 'name_he': 'נפתלי בנט', 'color': '#2f5f8a'},
)
TRACKED_BY_NAME = {t['name']: t for t in TRACKED}


class FeedNotReady(Exception):
    pass


def _parse_json_field(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, dict)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def _parse_prices(raw) -> list[float] | None:
    parsed = _parse_json_field(raw)
    if not isinstance(parsed, list) or not parsed:
        return None
    out = []
    for x in parsed:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            return None
    return out


def _yes_prob(market: dict) -> float | None:
    prices = _parse_prices(market.get('outcomePrices'))
    outcomes = _parse_json_field(market.get('outcomes'))
    if prices and isinstance(outcomes, list):
        for name, price in zip(outcomes, prices):
            if str(name).strip().lower() == 'yes':
                return max(0.0, min(1.0, price))
        return max(0.0, min(1.0, prices[0]))
    last = market.get('lastTradePrice')
    if last is not None:
        try:
            return max(0.0, min(1.0, float(last)))
        except (TypeError, ValueError):
            return None
    return None


def _yes_token(market: dict) -> str | None:
    tokens = _parse_json_field(market.get('clobTokenIds'))
    if isinstance(tokens, list) and tokens:
        return str(tokens[0])
    return None


def _http_get_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/json',
            'User-Agent': (
                'Mozilla/5.0 (compatible; ElectionDashboard/1.2; '
                '+https://github.com/6725838-blip/election-turnout-2026)'
            ),
            'Origin': 'https://polymarket.com',
            'Referer': 'https://polymarket.com/',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            if resp.status != 200:
                raise FeedNotReady(f'HTTP {resp.status}')
            raw = resp.read(MAX_BYTES + 1)
    except FeedNotReady:
        raise
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 403, 418, 429, 502, 503, 504):
            raise FeedNotReady(f'HTTP {exc.code}') from exc
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedNotReady(str(exc)) from exc
    if len(raw) > MAX_BYTES:
        raise FeedNotReady('response too large')
    try:
        return json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedNotReady('invalid JSON') from exc


def _fetch_history_node(token: str, interval: str, fidelity: int) -> list[dict]:
    """Prefer Node fetch — CLOB often 403s plain urllib from some networks."""
    node = shutil.which('node')
    if not node:
        raise FeedNotReady('node not available for CLOB history')
    url = f'{CLOB}?market={token}&interval={interval}&fidelity={fidelity}'
    script = (
        'const u=process.argv[1];'
        'fetch(u,{headers:{Accept:"application/json",'
        'Origin:"https://polymarket.com",Referer:"https://polymarket.com/"}})'
        '.then(async r=>{if(!r.ok){process.stderr.write("HTTP "+r.status);process.exit(2)}'
        'process.stdout.write(JSON.stringify(await r.json()))})'
        '.catch(e=>{process.stderr.write(String(e));process.exit(1)})'
    )
    try:
        proc = subprocess.run(
            [node, '-e', script, url],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FeedNotReady(f'node history failed: {exc}') from exc
    if proc.returncode != 0:
        raise FeedNotReady(f'node history exit {proc.returncode}: {proc.stderr[:200]}')
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise FeedNotReady('node history invalid JSON') from exc
    hist = data.get('history') if isinstance(data, dict) else None
    if not isinstance(hist, list):
        raise FeedNotReady('node history missing series')
    out = []
    for row in hist:
        try:
            t = int(row['t'])
            p = float(row['p'])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= p <= 1:
            out.append({'t': t, 'p': round(p, 4)})
    return out


def fetch_price_history(token: str) -> list[dict]:
    try:
        return _fetch_history_node(token, HISTORY_INTERVAL, HISTORY_FIDELITY)
    except FeedNotReady:
        url = f'{CLOB}?market={token}&interval={HISTORY_INTERVAL}&fidelity={HISTORY_FIDELITY}'
        data = _http_get_json(url)
        hist = data.get('history') if isinstance(data, dict) else None
        if not isinstance(hist, list):
            raise FeedNotReady('missing history')
        out = []
        for row in hist:
            try:
                t = int(row['t'])
                p = float(row['p'])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= p <= 1:
                out.append({'t': t, 'p': round(p, 4)})
        return out


def build_snapshot(event: dict, histories: dict[str, list[dict]]) -> dict:
    by_name = {}
    for m in event.get('markets') or []:
        name = (m.get('groupItemTitle') or '').strip()
        if name in TRACKED_BY_NAME:
            by_name[name] = m
    candidates = []
    for meta in TRACKED:
        m = by_name.get(meta['name'])
        if not m:
            continue
        prob = _yes_prob(m)
        if prob is None:
            continue
        token = _yes_token(m)
        try:
            vol = float(m.get('volume') or 0)
        except (TypeError, ValueError):
            vol = 0.0
        candidates.append({
            'name': meta['name'],
            'name_he': meta['name_he'],
            'color': meta['color'],
            'prob': round(prob, 4),
            'pct': round(prob * 100, 1),
            'volume': round(vol, 2),
            'image': m.get('image') or m.get('icon') or None,
            'yes_token': token,
            'market_id': str(m.get('id')) if m.get('id') is not None else None,
            'slug': m.get('slug'),
        })
    try:
        volume = float(event.get('volume') or 0)
    except (TypeError, ValueError):
        volume = 0.0
    return {
        'format_version': 3,
        'source': 'Polymarket',
        'delivery': 'same-origin-snapshot',
        'title': event.get('title') or 'Prime Minister of Israel after the next election?',
        'title_he': 'מי יהיה ראש הממשלה אחרי הבחירות הבאות?',
        'slug': event.get('slug'),
        'url': EVENT_URL,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'event_end': event.get('endDate'),
        'volume': round(volume, 2),
        'poll_seconds': 60,
        'history_interval': HISTORY_INTERVAL,
        'history_fidelity': HISTORY_FIDELITY,
        'histories': histories,
        'candidates': candidates,
        'disclaimer_he': (
            'סיכויי שוק הימורים (Polymarket), לא סקר ולא תחזית רשמית. '
            'הנתונים נמשכים בשרת ונשמרים באתר כדי לעבוד גם תחת חסימות רשת.'
        ),
    }


def fetch_event() -> dict:
    data = _http_get_json(API)
    if isinstance(data, list):
        if not data:
            raise FeedNotReady('empty event list')
        event = data[0]
    elif isinstance(data, dict):
        event = data
    else:
        raise FeedNotReady('unexpected payload')
    if not isinstance(event, dict) or not event.get('markets'):
        raise FeedNotReady('missing markets')
    return event


def main() -> int:
    prev = None
    if DEST.exists():
        try:
            prev = json.loads(DEST.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            prev = None
    try:
        event = fetch_event()
        snap = build_snapshot(event, {})
    except FeedNotReady as exc:
        print(f'Polymarket not ready ({exc}); keeping previous snapshot.', flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f'Polymarket update soft-failed: {exc}; keeping previous snapshot.', flush=True)
        return 0
    if len(snap['candidates']) < 2:
        print('Polymarket snapshot has too few candidates; keeping previous.', flush=True)
        return 0

    histories: dict[str, list[dict]] = {}
    for c in snap['candidates']:
        token = c.get('yes_token')
        if not token:
            continue
        try:
            histories[token] = fetch_price_history(token)
            print(f'History {c["name"]}: {len(histories[token])} points', flush=True)
        except FeedNotReady as exc:
            print(f'History soft-fail {c["name"]}: {exc}', flush=True)
            old = (prev or {}).get('histories') or {}
            if token in old:
                histories[token] = old[token]
    snap['histories'] = histories
    if not histories and prev and prev.get('histories'):
        snap['histories'] = prev['histories']
        print('Reused previous histories after fetch failures.', flush=True)

    DEST.write_text(json.dumps(snap, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    size_kb = DEST.stat().st_size / 1024
    print(
        f'Wrote {DEST.name}: {len(snap["candidates"])} candidates, '
        f'{len(histories)} histories, {size_kb:.0f} KB',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
