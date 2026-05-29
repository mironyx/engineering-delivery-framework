#!/usr/bin/env python3
"""Coverage manifest helpers for /feature-end Step 6.4.

Two operations:
  --extract-epic-slug   Read issue body from stdin, print epic slug or empty.
  --verify-anchors      Verify every lld: anchor in a manifest resolves.

Usage:
  gh issue view <N> --json body --jq .body | update-coverage-manifest.py --extract-epic-slug
  update-coverage-manifest.py --verify-anchors docs/design/v{N}/coverage-<slug>.yaml  # ADR-0036
  update-coverage-manifest.py --verify-anchors docs/design/coverage-<slug>.yaml         # legacy flat
"""

import argparse
import pathlib
import re
import sys


def extract_epic_slug() -> str:
    body = sys.stdin.read()
    m = re.search(r"lld-([a-z0-9-]+)-[a-z0-9-]+\.md", body)
    return m.group(1) if m else ""


def verify_anchors(manifest_path: str) -> bool:
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed — skipping anchor verification", file=sys.stderr)
        return True

    m = yaml.safe_load(pathlib.Path(manifest_path).read_text())
    ok = True
    for e in m.get("entries", []):
        lld = e.get("lld")
        if not lld:
            continue
        file, _, anchor = lld.partition("#")
        p = pathlib.Path("docs/design") / file
        if not p.exists():
            print(f"broken anchor: {lld} — file not found", file=sys.stderr)
            ok = False
        elif f'id="{anchor}"' not in p.read_text():
            print(f"broken anchor: {lld} — anchor not found in file", file=sys.stderr)
            ok = False
    if ok:
        print("manifest anchors OK")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Coverage manifest helpers")
    parser.add_argument("--extract-epic-slug", action="store_true")
    parser.add_argument("--verify-anchors", type=str, default=None, metavar="MANIFEST")
    args = parser.parse_args()

    if args.extract_epic_slug:
        slug = extract_epic_slug()
        if slug:
            print(slug)
    elif args.verify_anchors:
        if not verify_anchors(args.verify_anchors):
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
