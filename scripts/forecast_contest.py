#!/usr/bin/env python3
"""Shared contest rules: validate submissions, rebuild public snapshot."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIR = ROOT / 'forecasts' / 'submissions'
TRUTH_PATH = ROOT / 'forecasts' / 'truth.json'
PUBLIC_PATH = ROOT / 'forecasts-public.json'

CUTOFF_ISO = '2026-10-27T07:00:00+02:00'
PARTIES = [
    {'id': 'likud', 'name': 'הליכוד', 'bloc': 'right'},
    {'id': 'otzma', 'name': 'עוצמה יהודית', 'bloc': 'right'},
    {'id': 'tzionut', 'name': 'הציונות הדתית', 'bloc': 'right'},
    {'id': 'shas', 'name': 'ש״ס', 'bloc': 'right'},
    {'id': 'utj', 'name': 'יהדות התורה', 'bloc': 'right'},
    {'id': 'winter', 'name': 'עמך ישראל (וינטר)', 'bloc': 'right'},
    {'id': 'bennett', 'name': 'ביחד (בנט ויש עתיד)', 'bloc': 'center'},
    {'id': 'yashar', 'name': 'ישר (אייזנקוט)', 'bloc': 'center'},
    {'id': 'democrats', 'name': 'הדמוקרטים', 'bloc': 'center'},
    {'id': 'liberman', 'name': 'ישראל ביתנו', 'bloc': 'center'},
    {'id': 'zalicha', 'name': 'המילואימניקים והכלכלית (הנדל–זליכה)', 'bloc': 'center'},
    {'id': 'raam', 'name': 'רע״מ', 'bloc': 'arab'},
    {'id': 'joint', 'name': 'המשותפת (חד״ש–תע״ל–בל״ד)', 'bloc': 'arab'},
]
BLOCS = [
    {'id': 'right', 'name': 'ימין (כולל החרדים)'},
    {'id': 'center', 'name': 'מרכז־שמאל'},
    {'id': 'arab', 'name': 'ערבים'},
]


def normalize_name(name: str) -> str:
    return unicodedata.normalize('NFKC', str(name or '')).strip().casefold()


def cutoff_dt() -> datetime:
    return datetime.fromisoformat(CUTOFF_ISO)


def is_closed(now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current >= cutoff_dt().astimezone(timezone.utc)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {'ok': False, 'message': 'לא התקבלו נתוני תחזית.'}
    participant = str(payload.get('participant') or '').strip()
    method = str(payload.get('method') or '').strip()
    if not participant or len(participant) > 70:
        return {'ok': False, 'message': 'יש להזין כינוי באורך 1–70 תווים.'}
    if len(method) > 150:
        return {'ok': False, 'message': 'הנימוק ארוך מדי (מקסימום 150 תווים).'}

    raw_parties = payload.get('parties')
    party_map: dict[str, int] = {}
    if isinstance(raw_parties, list):
        for item in raw_parties:
            if isinstance(item, dict) and item.get('id') is not None:
                try:
                    party_map[str(item['id'])] = int(item.get('seats'))
                except (TypeError, ValueError):
                    return {'ok': False, 'message': 'מספר מנדטים אינו מספר שלם.'}
    elif isinstance(raw_parties, dict):
        for key, value in raw_parties.items():
            try:
                party_map[str(key)] = int(value)
            except (TypeError, ValueError):
                return {'ok': False, 'message': 'מספר מנדטים אינו מספר שלם.'}
    else:
        return {'ok': False, 'message': 'חסרה תחזית המפלגות.'}

    parties: dict[str, int] = {}
    party_total = 0
    for party in PARTIES:
        if party['id'] not in party_map:
            return {'ok': False, 'message': 'תחזית המפלגות אינה כוללת את כל המפלגות.'}
        n = party_map[party['id']]
        if not isinstance(n, int) or n < 0 or n > 120 or (n > 0 and n < 4):
            return {
                'ok': False,
                'message': (
                    f"מספר המנדטים אינו תקין עבור {party['name']}. "
                    'יש לבחור 0 או מספר שלם מ־4 עד 120.'
                ),
            }
        parties[party['id']] = n
        party_total += n
    if party_total != 120:
        return {'ok': False, 'message': 'תחזית המפלגות חייבת להסתכם בדיוק ב־120 מנדטים.'}

    input_blocs = payload.get('blocs') or {}
    if not isinstance(input_blocs, dict):
        return {'ok': False, 'message': 'תחזית הגושים אינה תקינה.'}
    blocs: dict[str, int] = {}
    bloc_total = 0
    for bloc in BLOCS:
        try:
            n = int(input_blocs.get(bloc['id']))
        except (TypeError, ValueError):
            return {'ok': False, 'message': f"תחזית הגושים אינה תקינה: {bloc['name']}."}
        if n < 0 or n > 120:
            return {'ok': False, 'message': f"תחזית הגושים אינה תקינה: {bloc['name']}."}
        blocs[bloc['id']] = n
        bloc_total += n
    if bloc_total != 120:
        return {'ok': False, 'message': 'תחזית הגושים חייבת להסתכם בדיוק ב־120 מנדטים.'}

    return {
        'ok': True,
        'participant': participant,
        'method': method,
        'parties': parties,
        'blocs': blocs,
        'version': str(payload.get('version') or '2026-v7-github'),
    }


def list_submissions() -> list[dict[str, Any]]:
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(SUBMISSIONS_DIR.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get('status') and data.get('status') != 'ok':
            continue
        participant = str(data.get('participant') or '').strip()
        parties = data.get('parties')
        blocs = data.get('blocs')
        if not participant or not isinstance(parties, dict) or not isinstance(blocs, dict):
            continue
        items.append({
            'timestamp': str(data.get('timestamp') or ''),
            'participant': participant,
            'method': str(data.get('method') or ''),
            'parties': {k: int(v) for k, v in parties.items()},
            'blocs': {k: int(v) for k, v in blocs.items()},
        })
    items.sort(key=lambda row: row['timestamp'])
    return items


def nickname_taken(participant: str, existing: list[dict[str, Any]] | None = None) -> bool:
    needle = normalize_name(participant)
    rows = existing if existing is not None else list_submissions()
    return any(normalize_name(row['participant']) == needle for row in rows)


def slugify_participant(participant: str) -> str:
    text = unicodedata.normalize('NFKC', participant).strip()
    text = re.sub(r'[^\w\u0590-\u05FF-]+', '-', text, flags=re.UNICODE)
    text = re.sub(r'-{2,}', '-', text).strip('-')
    return (text or 'participant')[:40]


def read_truth() -> dict[str, Any]:
    if not TRUTH_PATH.exists():
        return {'ready': False}
    try:
        data = json.loads(TRUTH_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'ready': False}
    raw = data.get('parties') if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {'ready': False}
    parties: dict[str, int] = {}
    total = 0
    for party in PARTIES:
        value = raw.get(party['id'], '')
        if value in ('', None):
            return {'ready': False}
        try:
            n = int(value)
        except (TypeError, ValueError):
            return {'ready': False}
        if n < 0 or n > 120:
            return {'ready': False}
        parties[party['id']] = n
        total += n
    if total != 120:
        return {'ready': False}
    blocs = {
        bloc['id']: sum(parties[p['id']] for p in PARTIES if p['bloc'] == bloc['id'])
        for bloc in BLOCS
    }
    return {'ready': True, 'parties': parties, 'blocs': blocs}


def calculate_consensus(forecasts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not forecasts:
        return None
    n = len(forecasts)
    return {
        'parties': {
            p['id']: sum(float((f.get('parties') or {}).get(p['id']) or 0) for f in forecasts) / n
            for p in PARTIES
        },
        'blocs': {
            b['id']: sum(float((f.get('blocs') or {}).get(b['id']) or 0) for f in forecasts) / n
            for b in BLOCS
        },
    }


def calculate_leaderboard(forecasts: list[dict[str, Any]], truth: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for forecast in forecasts:
        party_error = 0.0
        for party in PARTIES:
            actual = truth['parties'][party['id']]
            predicted = float((forecast.get('parties') or {}).get(party['id']) or 0)
            weight = 1.25 if 4 <= actual <= 8 else 1.0
            party_error += abs(predicted - actual) * weight
        party_error /= 2.0
        bloc_error = 0.0
        for bloc in BLOCS:
            bloc_error += abs(
                float((forecast.get('blocs') or {}).get(bloc['id']) or 0) - truth['blocs'][bloc['id']]
            )
        bloc_error = (bloc_error / 2.0) * 3.0
        predicted_winter = float((forecast.get('parties') or {}).get('winter') or 0) >= 4
        actual_winter = truth['parties']['winter'] >= 4
        predicted_zalicha = float((forecast.get('parties') or {}).get('zalicha') or 0) >= 4
        actual_zalicha = truth['parties']['zalicha'] >= 4
        predicted_right = sum(
            float((forecast.get('parties') or {}).get(p['id']) or 0)
            for p in PARTIES
            if p['bloc'] == 'right'
        )
        winter_penalty = 0 if predicted_winter == actual_winter else 6
        zalicha_penalty = 0 if predicted_zalicha == actual_zalicha else 6
        majority_penalty = 0 if (predicted_right >= 61) == (truth['blocs']['right'] >= 61) else 12
        rows.append({
            'participant': forecast['participant'],
            'timestamp': forecast.get('timestamp') or '',
            'partyError': party_error,
            'blocError': bloc_error,
            'winterPenalty': winter_penalty,
            'zalichaPenalty': zalicha_penalty,
            'majorityPenalty': majority_penalty,
            'total': party_error + bloc_error + winter_penalty + zalicha_penalty + majority_penalty,
        })
    rows.sort(key=lambda row: (row['total'], str(row['timestamp'])))
    return [dict(row, rank=index + 1) for index, row in enumerate(rows)]


def build_public_snapshot(status: str = 'ok') -> dict[str, Any]:
    forecasts = list_submissions()
    truth = read_truth()
    leaderboard = calculate_leaderboard(forecasts, truth) if truth.get('ready') else []
    return {
        'forecasts': forecasts,
        'consensus': calculate_consensus(forecasts),
        'truthReady': bool(truth.get('ready')),
        'leaderboard': leaderboard,
        'count': len(forecasts),
        'closed': is_closed(),
        'cutoff': CUTOFF_ISO,
        'parties': PARTIES,
        'blocs': BLOCS,
        'syncedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'delivery': 'same-origin-snapshot',
        'status': status,
    }


def write_public_snapshot(status: str = 'ok') -> dict[str, Any]:
    snap = build_public_snapshot(status=status)
    PUBLIC_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return snap


def save_submission(validated: dict[str, Any], timestamp: str | None = None) -> Path:
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = timestamp or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    stamp = re.sub(r'[^0-9]', '', ts)[:14] or '0'
    path = SUBMISSIONS_DIR / f'{slugify_participant(validated["participant"])}-{stamp}.json'
    if path.exists():
        path = SUBMISSIONS_DIR / f'{slugify_participant(validated["participant"])}-{stamp}-{path.stat().st_mtime_ns}.json'
    record = {
        'status': 'ok',
        'timestamp': ts,
        'participant': validated['participant'],
        'method': validated['method'],
        'parties': validated['parties'],
        'blocs': validated['blocs'],
        'version': validated.get('version') or '2026-v7-github',
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path
