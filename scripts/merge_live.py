"""Retain missing/older reports, with their original timestamps and an explicit stale flag."""
from copy import deepcopy
from city_norm import city_key
from validate_live import timestamp, validate

def station_partial(row):
    if row.get('reported_stations') is None and row.get('total_stations') is None:
        return False
    return (row.get('reported_stations') or 0) < (row.get('total_stations') or 0)


def report_full(row):
    return not row.get('partial') and not station_partial(row)


def merge_snapshot(previous, incoming):
    validate(incoming)
    if not previous or not previous.get('updated_at'):
        result=deepcopy(incoming)
    else:
        validate(previous)
        if not incoming.get('updated_at') or timestamp(incoming['updated_at']) < timestamp(previous['updated_at']):
            raise ValueError('Refusing missing or older snapshot timestamp')
        result=deepcopy(incoming)
        new={city_key(r['city']):r for r in result['records']}
        for old in previous['records']:
            key=city_key(old['city'])
            candidate=new.get(key)
            old_time=old.get('as_of') or previous['updated_at']
            next_partial=candidate is not None and (candidate.get('partial') or station_partial(candidate))
            if candidate is None or timestamp(candidate.get('as_of') or incoming['updated_at']) < timestamp(old_time) or (report_full(old) and next_partial):
                kept=deepcopy(old)
                kept.update(as_of=old_time, preserved_previous=True)
                new[key]=kept
        result['records']=list(new.values())
        if incoming.get('national_turnout_pct') is None and previous.get('national_turnout_pct') is not None:
            result['national_turnout_pct']=previous['national_turnout_pct']
            result['national_as_of']=previous.get('national_as_of') or previous['updated_at']
            result['national_preserved_previous']=True
    for row in result['records']:
        row.setdefault('as_of',result['updated_at'])
    if result.get('national_turnout_pct') is not None:
        result.setdefault('national_as_of',result['updated_at'])
    return validate(result)
