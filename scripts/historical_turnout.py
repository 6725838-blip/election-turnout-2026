"""Historical group turnout comparison for the 44 active research localities.

Computes official weighted turnout (sum voters / sum eligible) per primary group
for 2020–2022 using fixed current group membership. Pure functions for research
and for the dashboard historical panel — does not alter live weights.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_GROUPS = ('right', 'opp', 'haredi', 'arab', 'zionism')
YEARS = (2020, 2021, 2022)
NATIONAL_FINAL_PCT = {2020: 71.52, 2021: 67.44, 2022: 70.63}
GROUP_TITLES = {
    'right': 'ערי גוש נתניהו',
    'opp': 'ערי מרכז–שמאל (60% ומעלה)',
    'haredi': 'ערים חרדיות',
    'arab': 'ערים ערביות',
    'zionism': 'יישובים שבהם הציונות הדתית מעל 45%',
}


def load_baseline_rows(html_path: Path | None = None) -> list[dict[str, Any]]:
    path = html_path or (ROOT / 'index.html')
    html = path.read_text(encoding='utf-8')
    match = re.search(
        r'<script id="baseline-data" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    if not match:
        raise ValueError('baseline-data script not found')
    return json.loads(match.group(1))


def active_primary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r for r in rows
        if r.get('active') and r.get('group') in PRIMARY_GROUPS
    ]


def _num(x: Any) -> float | None:
    try:
        if x is None or x == '':
            return None
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # NaN check


def group_year_turnout(
    cities: list[dict[str, Any]],
    year: int,
) -> dict[str, Any] | None:
    """Official weighted turnout for one year on a fixed city set.

    Requires eligible{year} and voters{year} for every city. Missing values
    are not treated as zero — the year is marked incomplete.
    """
    elig_key = f'eligible{year}'
    voters_key = f'voters{year}'
    missing = [
        c.get('name') for c in cities
        if _num(c.get(elig_key)) is None or _num(c.get(voters_key)) is None
        or _num(c.get(elig_key)) <= 0
    ]
    if missing:
        return {
            'turnout_pct': None,
            'eligible': None,
            'voters': None,
            'n': len(cities),
            'missing_cities': missing,
            'complete': False,
        }
    eligible = sum(int(_num(c[elig_key])) for c in cities)
    voters = sum(int(_num(c[voters_key])) for c in cities)
    pct = 100.0 * voters / eligible if eligible > 0 else None
    national = NATIONAL_FINAL_PCT.get(year)
    return {
        'turnout_pct': pct,
        'eligible': eligible,
        'voters': voters,
        'n': len(cities),
        'missing_cities': [],
        'complete': True,
        'gap_vs_national_pp': (pct - national) if pct is not None and national is not None else None,
    }


def build_historical_comparison(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = rows if rows is not None else load_baseline_rows()
    active = active_primary_rows(data)
    groups: dict[str, Any] = {}
    for gid in PRIMARY_GROUPS:
        cities = [r for r in active if r['group'] == gid]
        years: dict[str, Any] = {}
        for year in YEARS:
            years[str(year)] = group_year_turnout(cities, year)
        y21 = years['2021'].get('turnout_pct')
        y22 = years['2022'].get('turnout_pct')
        delta = (y22 - y21) if y21 is not None and y22 is not None else None
        groups[gid] = {
            'id': gid,
            'n': len(cities),
            'cities': [c['name'] for c in cities],
            'years': years,
            'delta_2021_to_2022_pp': delta,
        }
    return {
        'format_version': 1,
        'method': 'official_voters_over_eligible_fixed_membership',
        'method_he': (
            'שיעור קבוצתי = סך מצביעים ÷ סך זכאים באותה שנה, '
            'על אותם יישובים פעילים בקבוצה כיום. מקור: קובצי ישובים של ועדת הבחירות (data.gov.il).'
        ),
        'national_final_pct': dict(NATIONAL_FINAL_PCT),
        'active_n': len(active),
        'groups': groups,
        'coverage_complete': all(
            groups[g]['years'][str(y)]['complete']
            for g in PRIMARY_GROUPS for y in YEARS
        ),
    }


def build_insights(comparison: dict[str, Any], limit: int = 3) -> list[dict[str, str]]:
    """At most a few non-obvious findings supported by the numbers."""
    groups = comparison['groups']
    deltas = {
        gid: g['delta_2021_to_2022_pp']
        for gid, g in groups.items()
        if g.get('delta_2021_to_2022_pp') is not None
    }
    insights: list[dict[str, str]] = []
    if deltas:
        up_id = max(deltas, key=deltas.get)
        flat_id = min(deltas, key=lambda k: abs(deltas[k]))
        if deltas[up_id] >= 1.5:
            insights.append({
                'title': 'העלייה הגדולה ביותר מ־2021 ל־2022',
                'body': (
                    f"ב{GROUP_TITLES[up_id]} השיעור עלה ב־{deltas[up_id]:.1f} נקודות אחוז — "
                    f"עדיין חשוב להסתכל גם על 2020 כרקע למחזוריות."
                ),
                'group': up_id,
            })
        if abs(deltas[flat_id]) < 0.5:
            insights.append({
                'title': 'יציבות יחסית בין 2021 ל־2022',
                'body': (
                    f"ב{GROUP_TITLES[flat_id]} השינוי היה כ־{deltas[flat_id]:+.1f} נקודות אחוז בלבד — "
                    f"בסיס שימושי לבדיקת משקולות בין מערכות."
                ),
                'group': flat_id,
            })

    # Stable gap vs national for right (if present)
    right = groups.get('right', {}).get('years', {})
    gaps = []
    for y in YEARS:
        g = right.get(str(y), {}).get('gap_vs_national_pp')
        if g is not None:
            gaps.append(g)
    if len(gaps) == 3 and max(gaps) - min(gaps) < 1.2:
        insights.append({
            'title': 'פער יציב מול הארצי',
            'body': (
                f"בערי גוש נתניהו הפער מול השיעור הארצי נשאר בסביבות "
                f"{sum(gaps)/3:.1f} נקודות אחוז בשלוש המערכות — "
                f"רמז לפער השתתפות יחסי יציב, לא רק לרמת הצבעה מוחלטת."
            ),
            'group': 'right',
        })

    arab = groups.get('arab', {}).get('years', {})
    a20 = arab.get('2020', {}).get('turnout_pct')
    a21 = arab.get('2021', {}).get('turnout_pct')
    a22 = arab.get('2022', {}).get('turnout_pct')
    if a20 and a21 and a22 and a22 > a21 and a22 < a20 - 5 and 'arab' not in {i['group'] for i in insights}:
        insights.append({
            'title': 'התאוששות חלקית אחרי 2021',
            'body': (
                f"בערים הערביות 2022 ({a22:.1f}%) גבוה מ־2021 ({a21:.1f}%), "
                f"אך עדיין רחוק מ־2020 ({a20:.1f}%). שלוש נקודות אינן מספיקות לדפוס ארוך טווח."
            ),
            'group': 'arab',
        })

    # Prefer diverse groups; cap
    seen = set()
    out = []
    for item in insights:
        if item['group'] in seen:
            continue
        seen.add(item['group'])
        out.append(item)
        if len(out) >= limit:
            break
    return out


def write_snapshot(path: Path | None = None) -> dict[str, Any]:
    comparison = build_historical_comparison()
    comparison['insights'] = build_insights(comparison)
    target = path or (ROOT / 'data' / 'historical_group_turnout.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
    return comparison


if __name__ == '__main__':
    snap = write_snapshot()
    print('active', snap['active_n'], 'coverage', snap['coverage_complete'])
    for gid, g in snap['groups'].items():
        print(
            gid,
            {y: round(g['years'][y]['turnout_pct'], 2) for y in map(str, YEARS)},
            'd21_22',
            round(g['delta_2021_to_2022_pp'], 2),
        )
