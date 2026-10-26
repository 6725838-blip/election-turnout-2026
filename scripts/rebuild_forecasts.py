#!/usr/bin/env python3
"""Rebuild forecasts-public.json from forecasts/submissions (+ optional truth)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forecast_contest import write_public_snapshot


def main() -> int:
    snap = write_public_snapshot(status='ok')
    print(
        f'Rebuilt forecasts-public.json: count={snap["count"]} '
        f'closed={snap["closed"]} truthReady={snap["truthReady"]}',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
