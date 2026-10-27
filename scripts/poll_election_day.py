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
YNET_CAT = 'https://www.ynet.co.il/news/category/184'
GOVMAP = 'https://elections.govmap.gov.il/data/votes/latest/municipal_data.json'
UA = {'User-Agent': 'PublicTurnoutDashboard/1.0', 'Accept': '*/*'}
IL = ZoneInfo('Asia/Jerusalem')

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
ARTICLE_RE = re.compile(r'/news/article/([a-zA-Z0-9]+)')
SEED_ARTICLES = (
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
    m = HEADLINE_RE.search(text) or ALT_NAT_RE.search(text)
    if not m:
        title = re.search(r'<title>(.*?)</title>', text, re.I | re.S)
        if title:
            flat = re.sub(r'\s+', ' ', title.group(1))
            m = HEADLINE_RE.search(flat) or ALT_NAT_RE.search(flat)
    if not m:
        return None
    hour = int(m.group(1))
    pct = float(m.group(2).replace(',', '.'))
    cites_cec = any(
        k in text for k in ('ועדת הבחירות', 'דין ליבנה', 'ליבנה', 'מסע״ת', 'מסיבת עיתונאים')
    )
    return {
        'time': f'{hour:02d}:00',
        'turnout_pct': pct,
        'source_url': url,
        'cites_cec': cites_cec,
        'snippet': re.sub(r'\s+', ' ', m.group(0)),
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
    for m in HEADLINE_RE.finditer(html):
        hour = int(m.group(1))
        pct = float(m.group(2).replace(',', '.'))
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
    by_time: dict[str, dict] = {}
    for row in found:
        if not row['cites_cec']:
            continue
        prev = by_time.get(row['time'])
        if prev is None or ('/article/' in row['source_url'] and '/article/' not in prev.get('source_url', '')):
            by_time[row['time']] = row
        elif prev['turnout_pct'] != row['turnout_pct'] and '/article/' in row['source_url']:
            by_time[row['time']] = row
    return [by_time[k] for k in sorted(by_time)]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


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
    if t not in existing or abs(float(existing[t]['turnout_pct']) - float(point['turnout_pct'])) > 1e-6:
        entry = {
            'time': t,
            'turnout_pct': float(point['turnout_pct']),
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
        # Refresh live timestamp only if we already have data? No — avoid noisy commits.
        report['changed'] = False
        if known:
            latest_t = max(known)
            report['current_latest'] = {'time': latest_t, 'turnout_pct': known[latest_t]}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
