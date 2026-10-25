"""Retain missing/older reports, with their original timestamps and an explicit stale flag."""
from copy import deepcopy
import re
import unicodedata
from validate_live import timestamp, validate

def city_key(name):
    return re.sub(r'''[\s״׳'"־–-]''', '', unicodedata.normalize('NFKC', name)).lower()

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
            old_full=not old.get('partial') and old.get('reported_stations',0)>=old.get('total_stations',0)
            partial=candidate and (candidate.get('partial') or candidate.get('reported_stations',0)<candidate.get('total_stations',0))
            if candidate is None or timestamp(candidate.get('as_of') or incoming['updated_at']) < timestamp(old_time) or (old_full and partial):
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
