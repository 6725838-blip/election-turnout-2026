"""Compatibility entry point; the maintained updater is in scripts/."""
import runpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'scripts'))
runpy.run_module('update_live', run_name='__main__')
