"""Run only on the verified election day, 07:00–23:59 Israel time."""
from datetime import datetime
from zoneinfo import ZoneInfo
import os

now=datetime.now(ZoneInfo('Asia/Jerusalem'))
enabled=now.date().isoformat()=='2026-10-27' and 7<=now.hour<24
with open(os.environ['GITHUB_OUTPUT'],'a') as output:
    output.write('active='+str(enabled).lower()+'\n')
print('Election-day schedule active:', enabled, '; Israel time:', now.isoformat())
