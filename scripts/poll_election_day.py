"""Election-day poller: national turnout from press citing CEC + GovMap cities.

Writes live-turnout.json / national_hourly_history.json when a newer verified
national point is found. Does not commit or push.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'live-turnout.json'
HISTORY = ROOT / 'data' / 'national_hourly_history.json'
CODES = ROOT / 'scripts' / 'city_codes.json'
YNET_CAT = 'https://www.ynet.co.il/news/category/184'
GOVMAP = 'https://elections.govmap.gov.il/data/votes/latest/municipal_data.json'
VOTES26_TURNOUT = 'https://votes26.com/api/v1/elections/26/turnout'
UA = {'User-Agent': 'PublicTurnoutDashboard/1.0', 'Accept': '*/*'}
IL = ZoneInfo('Asia/Jerusalem')

# CEC-citing press city % @16:00 (ynet hyzfwbrhmg) — only enforced near that hour
PRESS_CITY_HOUR = 16
PRESS_CITY_PCT = {
    'תל אביב-יפו': 50.4, 'ירושלים': 47.7, 'חיפה': 46.2, 'ראשון לציון': 50.9,
    'פתח תקווה': 52.8, 'נתניה': 41.5, 'אשדוד': 50.4, 'רמת גן': 52.9,
    'חולון': 48.5, 'באר שבע': 46.8, 'בני ברק': 53.3, 'רחובות': 54.0,
    'בת ים': 40.0, 'נצרת': 46.7, 'רהט': 60.6, 'מודיעין עילית': 58.8,
    'שדרות': 51.6, 'קריית שמונה': 43.2, 'נהריה': 49.1, 'עכו': 43.8,
    'אום אל־פחם': 41.7, 'שפרעם': 48.3, 'אלעד': 59.0, 'ביתר עילית': 52.0,
    'בית שמש': 47.1,
}
DELTA_NOISE_RE = re.compile(r'(?:זינק|עלי(?:יה|ה)|ירד|ירדה|צמח|קפץ)\s*(?:ב|של)?\s*-?\s*\d', re.U)

# e.g. שיעור ההצבעה עד 10:00 - 16.68% / עד השעה 12:00 ... 31.5%
HEADLINE_RE = re.compile(
    r'שיעור ההצבעה עד\s*(\d{1,2}):00\s*[-–—]\s*(\d{1,2}(?:[.,]\d+)?)\s*%',
    re.U,
)
# e.g. שיעור ההצבעה הארצי לשעה 12:00 עומד על 31.5%
ALT_NAT_RE = re.compile(
    r'שיעור ההצבעה(?:\s+הארצי)?(?:\s+לשעה|\s+עד(?:\s+השעה)?)\s*(\d{1,2}):00[^\d%]{0,40}?(\d{1,2}(?:[.,]\d+)?)\s*%',
    re.U,
)
# e.g. 55.7% הצביעו עד השעה 16:00 / נכון לשעה 16:00 עומד על 55.7%
PCT_FIRST_RE = re.compile(
    r'(\d{1,2}(?:[.,]\d+)?)\s*%\s*הצביעו עד(?:\s+השעה)?\s*(\d{1,2}):00',
    re.U,
)
# Cumulative only — avoid «עד 16:00 … זינק ב-17.2%» deltas
PCT_AFTER_RE = re.compile(
    r'(?:נכון ל|עד)(?:\s+השעה)?\s*(\d{1,2}):00'
    r'(?:(?!(?:זינק|עלי(?:יה|ה)|ירד|ירדה|צמח|קפץ)).){0,50}?'
    r'(?:שיעור ההצבעה|הצביעו|עומד על|אחוז ההצבעה)[^\d%]{0,20}?'
    r'(\d{1,2}(?:[.,]\d+)?)\s*%',
    re.U,
)
ARTICLE_RE = re.compile(r'/news/article/([a-zA-Z0-9]+)')
SEED_ARTICLES = (
    'https://www.ynet.co.il/news/article/r1m8p8a3fe',
    'https://www.ynet.co.il/news/article/sypynnr2zx',
    'https://www.ynet.co.il/news/article/hyzfwbrhmg',
    'https://www.ynet.co.il/news/article/bkkekx02mg',
    'https://www.ynet.co.il/news/article/hyiuqbc2zl',
    'https://www.ynet.co.il/news/article/s1dhwyrnme',
    'https://www.ynet.co.il/news/blogs/article/hkbbhw6nzg',
    'https://www.israelhayom.co.il/news/politics/article/21716830',
)


def _get(url: str, timeout: int = 40) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, (resp.headers.get('Content-Type') or ''), resp.read()


def govmap_ready() -> dict:
    out = {'url': GOVMAP, 'ready': False}
    try:
        status, ctype, raw = _get(GOVMAP)
        out['status'] = status
        out['ctype'] = ctype.split(';')[0]
        out['html'] = raw.lstrip().startswith(b'<')
        out['jsonish'] = raw.lstrip().startswith(b'{')
        out['ready'] = (not out['html']) and out['jsonish']
    except Exception as exc:  # noqa: BLE001
        out['error'] = str(exc)
    return out


def _extract_nat(text: str, url: str) -> dict | None:
    def from_match(m: re.Match, hour_first: bool) -> tuple[int, float, str]:
        if hour_first:
            return int(m.group(1)), float(m.group(2).replace(',', '.')), m.group(0)
        return int(m.group(2)), float(m.group(1).replace(',', '.')), m.group(0)

    candidates: list[tuple[int, float, str]] = []
    for rx, hour_first in (
        (HEADLINE_RE, True),
        (ALT_NAT_RE, True),
        (PCT_AFTER_RE, True),
        (PCT_FIRST_RE, False),
    ):
        m = rx.search(text)
        if m:
            hour, pct, snip = from_match(m, hour_first)
            if DELTA_NOISE_RE.search(snip):
                continue
            if not (5.0 <= pct <= 95.0):
                continue
            candidates.append((hour, pct, snip))
    if not candidates:
        title = re.search(r'<title>(.*?)</title>', text, re.I | re.S)
        if title:
            flat = re.sub(r'\s+', ' ', title.group(1))
            for rx, hour_first in (
                (HEADLINE_RE, True),
                (ALT_NAT_RE, True),
                (PCT_AFTER_RE, True),
                (PCT_FIRST_RE, False),
            ):
                m = rx.search(flat)
                if m:
                    hour, pct, snip = from_match(m, hour_first)
                    if DELTA_NOISE_RE.search(snip):
                        continue
                    if not (5.0 <= pct <= 95.0):
                        continue
                    candidates.append((hour, pct, snip))
    if not candidates:
        return None
    # Prefer the chronologically latest hour; for ties prefer higher cumulative %
    hour, pct, snip = max(candidates, key=lambda t: (t[0], t[1]))
    cites_cec = any(
        k in text for k in ('ועדת הבחירות', 'דין ליבנה', 'ליבנה', 'מסע״ת', 'מסיבת עיתונאים')
    )
    return {
        'time': f'{hour:02d}:00',
        'turnout_pct': pct,
        'source_url': url,
        'cites_cec': cites_cec,
        'snippet': re.sub(r'\s+', ' ', snip),
    }


def scan_ynet() -> list[dict]:
    """Return candidate national points from ynet (+ seeded CEC-citing articles)."""
    found: list[dict] = []
    urls: list[str] = list(SEED_ARTICLES)
    try:
        _, _, raw = _get(YNET_CAT)
        html = raw.decode('utf-8', 'replace')
    except Exception:
        html = ''
    # Category teasers often carry the latest CEC headline before article HTML is scraped
    if html:
        cat_row = _extract_nat(html, YNET_CAT)
        if cat_row and cat_row.get('cites_cec'):
            found.append(cat_row)
        for rx in (HEADLINE_RE, PCT_FIRST_RE, ALT_NAT_RE):
            for m in rx.finditer(html):
                if rx is PCT_FIRST_RE:
                    hour, pct = int(m.group(2)), float(m.group(1).replace(',', '.'))
                else:
                    hour, pct = int(m.group(1)), float(m.group(2).replace(',', '.'))
                if DELTA_NOISE_RE.search(m.group(0)) or not (5.0 <= pct <= 95.0):
                    continue
                prefix = html[max(0, m.start() - 500):m.start()]
                ids = ARTICLE_RE.findall(prefix)
                url = f'https://www.ynet.co.il/news/article/{ids[-1]}' if ids else YNET_CAT
                found.append({
                    'time': f'{hour:02d}:00',
                    'turnout_pct': pct,
                    'source_url': url,
                    'cites_cec': True,
                    'snippet': m.group(0),
                })
    for art_id in dict.fromkeys(ARTICLE_RE.findall(html)):
        urls.append(f'https://www.ynet.co.il/news/article/{art_id}')
    for url in dict.fromkeys(urls):
        try:
            _, _, body = _get(url, timeout=25)
            text = body.decode('utf-8', 'replace')
        except Exception:
            continue
        row = _extract_nat(text, url)
        if row:
            found.append(row)
    by_time: dict[str, dict] = {}
    for row in found:
        if not row['cites_cec']:
            continue
        prev = by_time.get(row['time'])
        if prev is None:
            by_time[row['time']] = row
            continue
        # Prefer article URLs; never replace a higher cumulative % with a lower one
        prev_art = '/article/' in prev.get('source_url', '')
        row_art = '/article/' in row.get('source_url', '')
        if float(row['turnout_pct']) > float(prev['turnout_pct']) + 1e-6:
            by_time[row['time']] = row
        elif abs(float(row['turnout_pct']) - float(prev['turnout_pct'])) <= 1e-6 and row_art and not prev_art:
            by_time[row['time']] = row
    return [by_time[k] for k in sorted(by_time)]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def apply_cities_from_votes26(now: datetime) -> dict:
    """Refresh baseline city rows from CEC station-file localities via Votes26."""
    codes = _load_json(CODES)
    by_code = {str(k): v for k, v in codes['by_code'].items()}
    name_to_code = {v: str(k) for k, v in by_code.items()}
    status, ctype, raw = _get(VOTES26_TURNOUT, timeout=40)
    if 'json' not in (ctype or '').lower() and not raw.lstrip().startswith(b'{'):
        return {'changed': False, 'error': f'unexpected ctype {ctype}'}
    data = json.loads(raw.decode('utf-8'))
    reports = [r for r in data.get('reports') or [] if r.get('localities')]
    if not reports:
        return {'changed': False, 'error': 'no localities'}
    reports.sort(key=lambda r: r.get('at') or '')
    rep = reports[-1]
    at = datetime.fromisoformat(str(rep['at']).replace('Z', '+00:00')).astimezone(IL)
    as_of = at.replace(microsecond=0).isoformat()
    rep_hour = float(rep.get('hour') or 0)

    loc_pct: dict[str, float] = {}
    for row in rep['localities']:
        name = by_code.get(str(row[0]))
        if name:
            loc_pct[name] = round(float(row[1]) * 100.0, 2)
    # Press cross-check only for the snapshot hour those % were curated for
    if abs(rep_hour - PRESS_CITY_HOUR) <= 0.5:
        for name, press in PRESS_CITY_PCT.items():
            got = loc_pct.get(name)
            if got is not None and abs(got - press) > 0.35:
                return {'changed': False, 'error': f'press mismatch {name}: {press} vs {got}'}
    else:
        # Later waves: most cities should not drop vs previous live rows
        prev_live = _load_json(LIVE) if LIVE.exists() else {}
        drops = 0
        compared = 0
        for row in prev_live.get('records') or []:
            name, old = row.get('city'), row.get('turnout_pct')
            if name not in loc_pct or not isinstance(old, (int, float)):
                continue
            compared += 1
            if loc_pct[name] + 0.5 < float(old):
                drops += 1
        if compared >= 10 and drops > compared * 0.25:
            return {
                'changed': False,
                'error': f'monotonic city check failed: {drops}/{compared} drops',
            }

    reg_counts: dict[str, dict] = {}
    for reg in rep.get('regions') or []:
        rid = str(reg.get('id') or '')
        if not rid.startswith('city-'):
            continue
        name = by_code.get(rid.split('-', 1)[1])
        e, v = reg.get('eligible'), reg.get('voters')
        if not name or not isinstance(e, (int, float)) or not isinstance(v, (int, float)) or e <= 0:
            continue
        reported = int(reg['reported']) if isinstance(reg.get('reported'), (int, float)) else None
        stations = int(reg['stations']) if isinstance(reg.get('stations'), (int, float)) else None
        if reported is not None and stations is not None and reported > stations:
            reported = stations = None  # drop inconsistent station fields
        reg_counts[name] = {
            'eligible': int(e),
            'voted': int(v),
            'reported_stations': reported,
            'total_stations': stations,
        }

    records = []
    for name in sorted(name_to_code):
        pct = loc_pct.get(name)
        if pct is None:
            continue
        row: dict = {
            'city': name,
            'turnout_pct': pct,
            'as_of': as_of,
            'partial': True,
            'source_note': 'דיווחי קלפיות ועדת הבחירות (סיכום יישוב); coverage חלקי',
        }
        counts = reg_counts.get(name)
        if counts:
            row['eligible'] = counts['eligible']
            row['voted'] = counts['voted']
            row['turnout_pct'] = round(100.0 * counts['voted'] / counts['eligible'], 2)
            if counts['reported_stations'] is not None:
                row['reported_stations'] = counts['reported_stations']
            if counts['total_stations'] is not None:
                row['total_stations'] = counts['total_stations']
        records.append(row)

    prev = _load_json(LIVE) if LIVE.exists() else {}
    prev_fp = json.dumps(
        [(r.get('city'), r.get('turnout_pct'), r.get('voted'), r.get('as_of')) for r in (prev.get('records') or [])],
        ensure_ascii=False, sort_keys=True,
    )
    new_fp = json.dumps(
        [(r.get('city'), r.get('turnout_pct'), r.get('voted'), r.get('as_of')) for r in records],
        ensure_ascii=False, sort_keys=True,
    )
    if prev_fp == new_fp:
        return {'changed': False, 'cities': len(records), 'as_of': as_of}

    live = dict(prev) if prev else {'format_version': 1}
    live['format_version'] = 1
    live['updated_at'] = now.isoformat(timespec='seconds')
    live['records'] = records
    live['source'] = (
        'ועדת הבחירות המרכזית — ארצי ממסע״ת (עיתונות); '
        'יישובים מדיווחי קלפיות (Votes26, מאומת מול ynet)'
    )
    live['notes'] = [
        f"ארצי {live.get('national_turnout_pct')}% · {live.get('national_as_of')}",
        f"{len(records)} יישובי בסיס מסיכום קלפיות ועדה (as_of {as_of}); partial.",
        'GovMap municipal_data.json לכנסת 26 עדיין לא JSON.',
    ]
    LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'changed': True,
        'cities': len(records),
        'with_counts': sum(1 for r in records if 'eligible' in r),
        'as_of': as_of,
        'status': status,
    }


def apply_national(point: dict, now: datetime) -> dict:
    hist = _load_json(HISTORY)
    elections = hist.setdefault('elections', {})
    block = elections.setdefault('2026-10', {
        'label': 'אוקטובר 2026 · כנסת 26',
        'date': '2026-10-27',
        'final_turnout_pct': None,
        'final_source_url': None,
        'final_source_type': None,
        'points': [],
    })
    points = block.setdefault('points', [])
    existing = {p['time']: p for p in points}
    changed = False
    t = point['time']
    new_pct = float(point['turnout_pct'])
    # Reject non-monotonic national points (turnout only rises during the day)
    earlier = [p for p in points if p['time'] < t]
    if earlier:
        max_earlier = max(float(p['turnout_pct']) for p in earlier)
        if new_pct + 0.05 < max_earlier:
            return {'changed': False, 'skipped': 'non_monotonic', 'latest': max(points, key=lambda p: p['time'])}
    if t in existing and float(existing[t]['turnout_pct']) > new_pct + 1e-6:
        return {'changed': False, 'skipped': 'lower_than_existing', 'latest': max(points, key=lambda p: p['time'])}
    if t not in existing or abs(float(existing[t]['turnout_pct']) - new_pct) > 1e-6:
        entry = {
            'time': t,
            'turnout_pct': new_pct,
            'source_url': point['source_url'],
            'source_type': 'secondary_citing_official',
            'verified': True,
            'note': f"דיווח עיתונאי המצטט את ועדת הבחירות ({point.get('snippet', '')})",
        }
        if t in existing:
            points[:] = [entry if p['time'] == t else p for p in points]
        else:
            points.append(entry)
            points.sort(key=lambda p: p['time'])
        changed = True
        HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # Refresh national fields; preserve any curated city records already on disk.
    latest = max(points, key=lambda p: p['time'])
    hour, minute = map(int, latest['time'].split(':'))
    as_of = datetime(2026, 10, 27, hour, minute, tzinfo=IL)
    prev = _load_json(LIVE) if LIVE.exists() else {}
    records = prev.get('records') if isinstance(prev.get('records'), list) else []
    notes = [
        f"ארצי {latest['turnout_pct']}% נכון לשעה {latest['time']}",
        'GovMap municipal_data.json לכנסת 26 עדיין לא JSON — ערים מגיעות מפרסומים המצטטים את הוועדה כשיש.',
    ]
    if records:
        notes.append(f'{len(records)} רשומות יישוב שמורות/מפורסמות (ייתכן partial).')
    live = {
        'format_version': 1,
        'source': 'ועדת הבחירות המרכזית — דיווח מסע״ת/הודעה רשמית כפי שפורסם בעיתונות',
        'updated_at': now.isoformat(timespec='seconds'),
        'national_turnout_pct': float(latest['turnout_pct']),
        'national_as_of': as_of.isoformat(timespec='seconds'),
        'national_source_url': latest['source_url'],
        'records': records,
        'notes': notes,
    }
    live_changed = (
        prev.get('national_turnout_pct') != live['national_turnout_pct']
        or prev.get('national_as_of') != live['national_as_of']
        or prev.get('national_source_url') != live['national_source_url']
    )
    if live_changed or changed:
        LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        changed = True
    return {
        'changed': changed,
        'latest': latest,
        'live_path': str(LIVE.relative_to(ROOT)).replace('\\', '/'),
    }


def main() -> int:
    now = datetime.now(IL)
    report: dict = {
        'polled_at': now.isoformat(timespec='seconds'),
        'govmap': govmap_ready(),
        'candidates': [],
        'changed': False,
    }
    try:
        candidates = scan_ynet()
    except Exception as exc:  # noqa: BLE001
        report['scan_error'] = str(exc)
        candidates = []
    report['candidates'] = candidates

    hist = _load_json(HISTORY)
    known = {
        p['time']: float(p['turnout_pct'])
        for p in (hist.get('elections', {}).get('2026-10', {}) or {}).get('points', [])
    }
    new_points = [
        c for c in candidates
        if c['time'] not in known or abs(known[c['time']] - float(c['turnout_pct'])) > 1e-6
    ]
    report['new_points'] = new_points

    if new_points:
        # Apply all new points; live snapshot uses the chronologically latest
        for p in sorted(new_points, key=lambda x: x['time']):
            result = apply_national(p, now)
        report['changed'] = True
        report['applied'] = result
    else:
        report['changed'] = False
        if known:
            latest_t = max(known)
            report['current_latest'] = {'time': latest_t, 'turnout_pct': known[latest_t]}

    try:
        cities = apply_cities_from_votes26(now)
    except Exception as exc:  # noqa: BLE001
        cities = {'changed': False, 'error': str(exc)}
    report['cities'] = cities
    if cities.get('changed'):
        report['changed'] = True

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
