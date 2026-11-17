#!/usr/bin/env python3
"""Feature identity CLI (LLD v3-e3-3 §1.1).

Usage:
  feature-id.py id <ref>
  feature-id.py reference-lines <ref>...

Exits 1 with one `Error: …` line on a malformed ref or invalid backend config.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _feature_id  # noqa: E402
from _tracker_contract import TrackerError  # noqa: E402

_USAGE = "usage: feature-id.py id <ref> | reference-lines <ref>..."


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        if len(args) == 2 and args[0] == "id":
            print(_feature_id.resolve_feature_id(args[1], _feature_id.main_checkout_root()))
        elif len(args) >= 2 and args[0] == "reference-lines":
            print(_feature_id.issue_reference_lines(args[1:], _feature_id.main_checkout_root()))
        else:
            raise TrackerError(_USAGE)
    except TrackerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
