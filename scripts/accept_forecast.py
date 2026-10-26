#!/usr/bin/env python3
"""Accept one contest submission from repository_dispatch client_payload."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forecast_contest import (
    is_closed,
    list_submissions,
    nickname_taken,
    save_submission,
    validate_payload,
    write_public_snapshot,
)


def main() -> int:
    raw = (os.environ.get('CLIENT_PAYLOAD') or '').strip()
    if not raw:
        print('CLIENT_PAYLOAD is empty', flush=True)
        return 1
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f'Invalid CLIENT_PAYLOAD JSON: {exc}', flush=True)
        return 1

    honeypot = str(envelope.get('honeypot') or envelope.get('website') or '').strip()
    if honeypot:
        print('Rejected honeypot submission', flush=True)
        return 0

    submission = envelope.get('submission')
    if not isinstance(submission, dict):
        # Allow a flat payload for manual workflow_dispatch testing.
        submission = envelope if 'participant' in envelope else None
    if not isinstance(submission, dict):
        print('Missing submission object', flush=True)
        return 1

    if is_closed():
        print('Contest closed; ignoring submission', flush=True)
        write_public_snapshot(status='closed')
        return 0

    validated = validate_payload(submission)
    if not validated.get('ok'):
        print(f"Rejected: {validated.get('message')}", flush=True)
        return 0

    existing = list_submissions()
    if nickname_taken(validated['participant'], existing):
        print('Rejected: duplicate nickname', flush=True)
        return 0

    path = save_submission(validated, timestamp=str(submission.get('submittedAt') or '') or None)
    snap = write_public_snapshot(status='ok')
    print(f'Accepted {path.name}; public count={snap["count"]}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
