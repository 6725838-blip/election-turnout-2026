"""Package only public website assets, excluding scripts and local backups."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / '_site'
target.mkdir(exist_ok=True)
for name in ('index.html', 'live-turnout.json', 'turnout-history.json', '.nojekyll'):
    shutil.copyfile(ROOT / name, target / name)
data_src = ROOT / 'data' / 'national_hourly_history.json'
if data_src.exists():
    (target / 'data').mkdir(exist_ok=True)
    shutil.copyfile(data_src, target / 'data' / 'national_hourly_history.json')
test=target/'test'
test.mkdir(exist_ok=True)
html=(ROOT/'index.html').read_text(encoding='utf-8')
html=html.replace('<body>', '<body>')
html=html.replace('<header class="head">','<div id="testEnvironmentBanner" role="alert" style="background:#9b1c31;color:white;padding:20px;text-align:center;font-size:22px;font-weight:bold">סביבת בדיקה בלבד — כל נתוני ההצבעה בעמוד זה מדומים</div><header class="head">')
(test/'index.html').write_text(html,encoding='utf-8')
shutil.copyfile(ROOT/'test/live-turnout.json',test/'live-turnout.json')
shutil.copyfile(ROOT/'turnout-history.json', test/'turnout-history.json')
print('Packaged index.html, live-turnout.json, turnout-history.json and .nojekyll')
