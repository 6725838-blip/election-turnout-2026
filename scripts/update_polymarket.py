#!/usr/bin/env python3
"""Fetch Polymarket Israel PM odds for the three tracked candidates.

Soft-fails (exit 0, keep previous file) when the remote API is unreachable.
Live charts refresh in the browser every minute via gamma/clob CORS;
this snapshot is a cache for first paint and offline fallback.
"""
from __future__ import annotations

import json
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
MAX_BYTES = 2_500_000

# Fixed board order (not sorted by odds).
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


def build_snapshot(event: dict) -> dict:
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
        'format_version': 2,
        'source': 'Polymarket',
        'title': event.get('title') or 'Prime Minister of Israel after the next election?',
        'title_he': 'מי יהיה ראש הממשלה אחרי הבחירות הבאות?',
        'slug': event.get('slug'),
        'url': EVENT_URL,
        'gamma_url': API,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'event_end': event.get('endDate'),
        'volume': round(volume, 2),
        'poll_seconds': 60,
        'candidates': candidates,
        'disclaimer_he': (
            'סיכויי שוק הימורים (Polymarket), לא סקר ולא תחזית רשמית. '
            'אינם קשורים לנתוני ההשתתפות בדשבורד. מתעדכן בדפדפן כל דקה.'
        ),
    }


def fetch_event() -> dict:
    req = urllib.request.Request(
        API,
        headers={
            'Accept': 'application/json',
            'User-Agent': 'ElectionDashboard-Polymarket/1.1',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                raise FeedNotReady(f'HTTP {resp.status}')
            raw = resp.read(MAX_BYTES + 1)
    except FeedNotReady:
        raise
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 403, 429, 502, 503, 504):
            raise FeedNotReady(f'HTTP {exc.code}') from exc
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedNotReady(str(exc)) from exc
    if len(raw) > MAX_BYTES:
        raise FeedNotReady('response too large')
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedNotReady('invalid JSON') from exc
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
    try:
        snap = build_snapshot(fetch_event())
    except FeedNotReady as exc:
        print(f'Polymarket not ready ({exc}); keeping previous snapshot.', flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 — soft-fail for CI
        print(f'Polymarket update soft-failed: {exc}; keeping previous snapshot.', flush=True)
        return 0
    if len(snap['candidates']) < 2:
        print('Polymarket snapshot has too few candidates; keeping previous.', flush=True)
        return 0
    DEST.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {DEST.name}: {len(snap["candidates"])} candidates, volume={snap["volume"]}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
