"""Package only public website assets, excluding scripts and local backups."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / '_site'
target.mkdir(exist_ok=True)
for name in ('index.html', 'live-turnout.json', '.nojekyll'):
    shutil.copyfile(ROOT / name, target / name)
print('Packaged index.html, live-turnout.json and .nojekyll')
