"""Package only public website assets, excluding scripts and local backups."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / '_site'
target.mkdir(exist_ok=True)
for name in (
    'index.html', 'live-turnout.json', 'turnout-history.json', 'polymarket-pm.json', '.nojekyll',
    'favicon-32.png', 'favicon-64.png', 'apple-touch-icon.png', 'logo-mark.png',
):
    src = ROOT / name
    if src.exists():
        shutil.copyfile(src, target / name)
(target / 'data').mkdir(exist_ok=True)
for name in ('national_hourly_history.json', 'historical_group_turnout.json'):
    data_src = ROOT / 'data' / name
    if data_src.exists():
        shutil.copyfile(data_src, target / 'data' / name)
test=target/'test'
test.mkdir(exist_ok=True)
html=(ROOT/'index.html').read_text(encoding='utf-8')
html=html.replace('<body>', '<body>')
html=html.replace('<header class="head">','<div id="testEnvironmentBanner" role="alert" style="background:#9b1c31;color:white;padding:20px;text-align:center;font-size:22px;font-weight:bold">סביבת בדיקה בלבד — כל נתוני ההצבעה בעמוד זה מדומים</div><header class="head">')
(test/'index.html').write_text(html,encoding='utf-8')
shutil.copyfile(ROOT/'test/live-turnout.json',test/'live-turnout.json')
shutil.copyfile(ROOT/'turnout-history.json', test/'turnout-history.json')
print('Packaged public site assets into _site/')
