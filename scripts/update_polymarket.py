#!/usr/bin/env python3
"""Fetch Polymarket Israel PM market odds into a slim public JSON snapshot.

Soft-fails (exit 0, keep previous file) when the remote API is unreachable or
returns an unexpected shape — so scheduled CI stays green.
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

HE_NAMES = {
    'Benjamin Netanyahu': 'בנימין נתניהו',
    'Naftali Bennett': 'נפתלי בנט',
    'Yair Lapid': 'יאיר לפיד',
    'Gadi Eizenkot': 'גדי איזנקוט',
    'Benny Gantz': 'בני גנץ',
    'Avigdor Lieberman': 'אביגדור ליברמן',
    'Yossi Cohen': 'יוסי כהן',
    'Yair Golan': 'יאיר גולן',
    'Itamar Ben-Gvir': 'איתמר בן גביר',
    'Itamar Ben Gvir': 'איתמר בן גביר',
    'Bezalel Smotrich': 'בצלאל סמוטריץ׳',
    'Ayelet Shaked': 'איילת שקד',
    "Gideon Sa'ar": 'גדעון סער',
    'Gideon Saar': 'גדעון סער',
    'Merav Michaeli': 'מרב מיכאלי',
    'Mansour Abbas': 'מנסור עבאס',
    'Ayman Odeh': 'איימן עודה',
    'Israel Katz': 'ישראל כץ',
    'Moshe Feiglin': 'משה פייגלין',
    'Ofer Winter': 'עופר וינטר',
    'Amir Ohana': 'אמיר אוחנה',
    'Gilad Erdan': 'גלעד ארדן',
}


class FeedNotReady(Exception):
    pass


def _parse_prices(raw) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, list) or not raw:
        return None
    out = []
    for x in raw:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            return None
    return out


def _yes_prob(market: dict) -> float | None:
    prices = _parse_prices(market.get('outcomePrices'))
    outcomes = market.get('outcomes')
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            outcomes = None
    if prices and outcomes and isinstance(outcomes, list):
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


def build_snapshot(event: dict) -> dict:
    markets = event.get('markets') or []
    candidates = []
    for m in markets:
        if m.get('closed') is True and m.get('active') is False:
            continue
        name = (m.get('groupItemTitle') or m.get('question') or '').strip()
        if not name:
            continue
        # Skip generic multi-outcome question shells without a person label
        if name == event.get('title'):
            continue
        prob = _yes_prob(m)
        if prob is None:
            continue
        try:
            vol = float(m.get('volume') or 0)
        except (TypeError, ValueError):
            vol = 0.0
        candidates.append({
            'name': name,
            'name_he': HE_NAMES.get(name, name),
            'prob': round(prob, 4),
            'pct': round(prob * 100, 1),
            'volume': round(vol, 2),
            'image': m.get('image') or m.get('icon') or None,
        })
    candidates.sort(key=lambda c: (-c['prob'], c['name']))
    try:
        volume = float(event.get('volume') or 0)
    except (TypeError, ValueError):
        volume = 0.0
    return {
        'format_version': 1,
        'source': 'Polymarket',
        'title': event.get('title') or 'Prime Minister of Israel after the next election?',
        'title_he': 'מי יהיה ראש הממשלה אחרי הבחירות הבאות?',
        'slug': event.get('slug'),
        'url': EVENT_URL,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'event_end': event.get('endDate'),
        'volume': round(volume, 2),
        'candidates': candidates,
        'disclaimer_he': (
            'סיכויי שוק הימורים (Polymarket), לא סקר ולא תחזית רשמית. '
            'אינם קשורים לנתוני ההשתתפות בדשבורד.'
        ),
    }


def fetch_event() -> dict:
    req = urllib.request.Request(
        API,
        headers={
            'Accept': 'application/json',
            'User-Agent': 'ElectionDashboard-Polymarket/1.0',
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
