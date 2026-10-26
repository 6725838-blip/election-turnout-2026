"""Additive remaining-pp national turnout forecast from curated hourly history."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / 'data' / 'national_hourly_history.json'
DEFAULT_MAX_GAP = 120
DEFAULT_MIN_ELECTIONS = 3


def load_history(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or HISTORY_PATH).read_text(encoding='utf-8'))


def time_to_minutes(hhmm: str) -> int | None:
    try:
        parts = str(hhmm).strip().split(':')
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError, IndexError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def minutes_to_time(mins: int) -> str:
    h, m = divmod(int(mins), 60)
    return f'{h:02d}:{m:02d}'


def verified_points(election: dict[str, Any]) -> list[tuple[int, float, dict[str, Any]]]:
    out = []
    for p in election.get('points') or []:
        if p.get('verified') is False:
            continue
        mins = time_to_minutes(p.get('time'))
        try:
            pct = float(p.get('turnout_pct'))
        except (TypeError, ValueError):
            continue
        if mins is None or not (0 <= pct <= 100):
            continue
        out.append((mins, pct, p))
    out.sort(key=lambda x: x[0])
    return out


def estimate_at_hour(
    election: dict[str, Any],
    target_minutes: int,
    max_gap_minutes: int = DEFAULT_MAX_GAP,
) -> dict[str, Any] | None:
    points = verified_points(election)
    if not points:
        return None
    exact = [p for p in points if p[0] == target_minutes]
    if exact:
        mins, pct, meta = exact[0]
        return {
            'turnout_pct': pct,
            'method': 'exact',
            'matched_time': minutes_to_time(mins),
            'source_url': meta.get('source_url'),
            'source_type': meta.get('source_type'),
            'interpolated': False,
        }
    before = [p for p in points if p[0] < target_minutes]
    after = [p for p in points if p[0] > target_minutes]
    if not before or not after:
        return None
    b, a = before[-1], after[0]
    gap = a[0] - b[0]
    if gap <= 0 or gap > max_gap_minutes:
        return None
    if not (b[0] <= target_minutes <= a[0]):
        return None
    ratio = (target_minutes - b[0]) / gap
    pct = b[1] + ratio * (a[1] - b[1])
    return {
        'turnout_pct': pct,
        'method': 'linear_interpolation',
        'matched_time': minutes_to_time(target_minutes),
        'from_time': minutes_to_time(b[0]),
        'to_time': minutes_to_time(a[0]),
        'source_url': b[2].get('source_url'),
        'source_type': 'interpolated',
        'interpolated': True,
    }


def forecast_scenarios(
    current_pct: float,
    target_minutes: int,
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hist = history or load_history()
    max_gap = int(hist.get('interpolation_max_gap_minutes') or DEFAULT_MAX_GAP)
    min_n = int(hist.get('min_elections_for_forecast') or DEFAULT_MIN_ELECTIONS)
    elections = hist.get('elections') or {}
    scenarios = []
    skipped = []
    for eid, election in elections.items():
        final = election.get('final_turnout_pct')
        try:
            final_f = float(final)
        except (TypeError, ValueError):
            skipped.append({'id': eid, 'reason': 'missing_final'})
            continue
        est = estimate_at_hour(election, target_minutes, max_gap)
        if est is None:
            skipped.append({'id': eid, 'reason': 'no_matching_hour'})
            continue
        remaining = final_f - est['turnout_pct']
        forecast = current_pct + remaining
        scenarios.append({
            'id': eid,
            'label': election.get('label') or eid,
            'date': election.get('date'),
            'historical_at_hour': round(est['turnout_pct'], 4),
            'historical_final': final_f,
            'historical_remaining_pp': round(remaining, 4),
            'forecast_pct': round(forecast, 4),
            'match': est,
            'final_source_url': election.get('final_source_url'),
        })
    if len(scenarios) < min_n:
        return {
            'ok': False,
            'reason': 'insufficient_elections',
            'n': len(scenarios),
            'min_required': min_n,
            'scenarios': scenarios,
            'skipped': skipped,
            'target_time': minutes_to_time(target_minutes),
            'current_pct': current_pct,
        }
    forecasts = [s['forecast_pct'] for s in scenarios]
    mid = sum(forecasts) / len(forecasts)
    return {
        'ok': True,
        'method': 'additive_remaining_pp',
        'n': len(scenarios),
        'total_elections': len(elections),
        'mid': mid,
        'lo': min(forecasts),
        'hi': max(forecasts),
        'scenarios': scenarios,
        'skipped': skipped,
        'target_time': minutes_to_time(target_minutes),
        'current_pct': current_pct,
        'warnings': [
            w for w in [
                'forecast_below_current' if mid + 1e-9 < current_pct else None,
                'range_outside_0_100' if lo_hi_bad(forecasts) else None,
            ] if w
        ],
    }


def lo_hi_bad(forecasts: list[float]) -> bool:
    return any(f < 0 or f > 100 for f in forecasts)


def backtest(
    history: dict[str, Any] | None = None,
    hours: list[str] | None = None,
) -> dict[str, Any]:
    hist = history or load_history()
    hours = hours or ['10:00', '12:00', '14:00', '16:00', '18:00', '20:00']
    elections = hist.get('elections') or {}
    rows = []
    for hour in hours:
        mins = time_to_minutes(hour)
        if mins is None:
            continue
        for hold_id, hold in elections.items():
            est = estimate_at_hour(hold, mins, int(hist.get('interpolation_max_gap_minutes') or DEFAULT_MAX_GAP))
            if est is None:
                continue
            try:
                true_final = float(hold['final_turnout_pct'])
            except (TypeError, ValueError, KeyError):
                continue
            # leave-one-out: rebuild history without hold_id
            others = {
                'interpolation_max_gap_minutes': hist.get('interpolation_max_gap_minutes', DEFAULT_MAX_GAP),
                'min_elections_for_forecast': min(3, max(1, len(elections) - 1)),
                'elections': {k: v for k, v in elections.items() if k != hold_id},
            }
            fc = forecast_scenarios(est['turnout_pct'], mins, others)
            if not fc.get('ok'):
                continue
            err = fc['mid'] - true_final
            in_range = fc['lo'] - 1e-9 <= true_final <= fc['hi'] + 1e-9
            rows.append({
                'holdout': hold_id,
                'hour': hour,
                'current_at_hour': est['turnout_pct'],
                'true_final': true_final,
                'forecast_mid': fc['mid'],
                'forecast_lo': fc['lo'],
                'forecast_hi': fc['hi'],
                'error_pp': err,
                'abs_error_pp': abs(err),
                'in_range': in_range,
                'n_scenarios': fc['n'],
            })
    if not rows:
        return {'n': 0, 'mae': None, 'max_abs_error': None, 'in_range_rate': None, 'rows': []}
    mae = sum(r['abs_error_pp'] for r in rows) / len(rows)
    max_abs = max(r['abs_error_pp'] for r in rows)
    in_range_rate = sum(1 for r in rows if r['in_range']) / len(rows)
    by_hour = {}
    for hour in hours:
        subset = [r for r in rows if r['hour'] == hour]
        if not subset:
            continue
        by_hour[hour] = {
            'n': len(subset),
            'mae': sum(r['abs_error_pp'] for r in subset) / len(subset),
            'max_abs_error': max(r['abs_error_pp'] for r in subset),
            'in_range_rate': sum(1 for r in subset if r['in_range']) / len(subset),
        }
    return {
        'n': len(rows),
        'mae': mae,
        'max_abs_error': max_abs,
        'in_range_rate': in_range_rate,
        'by_hour': by_hour,
        'rows': rows,
    }


if __name__ == '__main__':
    demo = forecast_scenarios(12.5, time_to_minutes('10:00'))
    print('demo10', 'ok' if demo.get('ok') else demo.get('reason'),
          round(demo.get('mid', 0), 2) if demo.get('ok') else None,
          demo.get('n'))
    bt = backtest()
    print('backtest n', bt['n'], 'mae', round(bt['mae'], 3) if bt['mae'] is not None else None,
          'max', round(bt['max_abs_error'], 3) if bt['max_abs_error'] is not None else None,
          'in_range', round(bt['in_range_rate'] * 100, 1) if bt['in_range_rate'] is not None else None)
