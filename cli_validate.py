#!/usr/bin/env python3
"""CLI entry point wrapping intake_steward.validate_submission for a GitHub
Action step. Reads the issue body + account/rate-limit state from files (so
the Action controls all I/O; this script has no direct GitHub API access of
its own), writes a single JSON result to stdout.

Usage:
    python3 cli_validate.py \\
        --type memory \\
        --body-file body.txt \\
        --login alice --created-at 2024-01-01T00:00:00+00:00 \\
        --sequence 7 \\
        --existing-file existing.json \\
        --ratelimit-file ratelimit.json \\
        --labels-file memory-labels.json

Exit code 0 always (the caller branches on the JSON "status" field, not on
exit code, so a rejection is not treated as a script crash).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from intake_steward import (
    AccountInfo,
    RateLimiter,
    derive_label_map,
    parse_issue_form_body,
    validate_submission,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, choices=["memory", "ideas", "tension", "creativity"])
    p.add_argument("--body-file", required=True)
    p.add_argument("--login", required=True)
    p.add_argument("--created-at", required=True, help="ISO 8601, e.g. 2024-01-01T00:00:00+00:00")
    p.add_argument("--sequence", required=True, type=int)
    p.add_argument("--existing-file", required=True, help="JSON list of existing description strings")
    p.add_argument("--ratelimit-file", required=True, help="JSON rate-limiter state, read AND rewritten")
    p.add_argument("--form-file", required=True,
                    help="Path to the ISSUE_TEMPLATE/*.yml this submission came from — "
                         "the label->id map is derived from it directly, not hand-maintained.")
    args = p.parse_args()

    with open(args.body_file, encoding="utf-8") as f:
        body = f.read()
    with open(args.existing_file, encoding="utf-8") as f:
        existing = json.load(f)
    with open(args.ratelimit_file, encoding="utf-8") as f:
        limiter = RateLimiter.from_json(f.read())
    with open(args.form_file, encoding="utf-8") as f:
        label_to_id = derive_label_map(f.read())

    fields = parse_issue_form_body(body, label_to_id)
    account = AccountInfo(login=args.login, created_at=datetime.fromisoformat(args.created_at))

    result = validate_submission(
        args.type,
        fields,
        account=account,
        existing_descriptions=existing,
        limiter=limiter,
        sequence=args.sequence,
    )

    # Rate-limiter state was mutated in place by validate_submission (via
    # limiter.record) whenever the submission counted against the cap —
    # persist it back so the next Action run sees the update.
    with open(args.ratelimit_file, "w", encoding="utf-8") as f:
        f.write(limiter.to_json())

    print(json.dumps({
        "status": result.status,
        "reasons": result.reasons,
        "filename": result.filename,
        "tier": result.tier,
        "fields": fields,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
