#!/usr/bin/env python3
"""Compatibility wrapper: rebuild public snapshot from local submissions."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forecast_contest import write_public_snapshot


def main() -> int:
    snap = write_public_snapshot(status='ok')
    print(
        f'Synced local forecast snapshot: count={snap["count"]} status={snap["status"]}',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
