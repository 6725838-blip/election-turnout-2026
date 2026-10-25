"""Two deterministic test snapshots, strictly separate from the live data path."""
import datetime as dt
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
stage=sys.argv[1]
if stage not in ('one','two','clear'): raise SystemExit('Expected one, two or clear')
rows=json.loads(re.search(r'<script id="baseline-data" type="application/json">(.*?)</script>', (ROOT/'index.html').read_text(encoding='utf-8'), re.S)[1])
factor={'one':0.5,'two':0.6}.get(stage)
feed=dict(format_version=1,demo=True,test_revision=stage if factor else 'cleared',
          source='הדגמה בלבד — בדיקה אוטומטית '+stage if factor else 'סביבת בדיקה בלבד — אין נתוני הדגמה פעילים',
          updated_at=dt.datetime.now(dt.timezone.utc).isoformat() if factor else None,
          national_turnout_pct=70.63*factor if factor else None,records=[])
if factor:
    for row in rows:
        if not row['active']: continue
        # Synthetic counts chosen to give exactly 50%/60% of each historical rate.
        eligible=1_000_000
        pct=row['p2022']*factor
        feed['records'].append(dict(city=row['name'],eligible=eligible,voted=eligible*pct/100,
                                    turnout_pct=pct,partial=False,as_of=feed['updated_at']))
(ROOT/'test/live-turnout.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Test snapshot only:',stage,'records:',len(feed['records']))
