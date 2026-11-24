#!/usr/bin/env python3
"""Claim a work item so two workers never take it: python3 platform/kit/claim.py {claim|release|list} [ITEM] --worker NAME [--ttl-hours H]

Uses claims_lib.py (the platform's lease protocol, copied unchanged): an annotated git tag claim/backlog/<item> on origin plus the shared
branch claims/<item>. Workers that cannot push tags (the GitHub connector) claim by creating the branch claims/<item> instead. Run from a
clone of this repo. Exit 1 with CLAIM_HELD / CLAIM_LOST when someone else holds it.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claims_lib as lib  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["claim", "release", "list"])
    ap.add_argument("item", nargs="?")
    ap.add_argument("--worker")
    ap.add_argument("--ttl-hours", type=float, default=lib.DEFAULT_TTL_HOURS)
    args = ap.parse_args(argv)
    repo = Path.cwd()
    try:
        if args.cmd == "list":
            print(json.dumps(lib.fetch_claims(repo), indent=1, default=str))
            return 0
        if not args.item or not args.worker:
            ap.error("claim and release need ITEM and --worker")
        out = lib.claim(repo, args.item, args.worker, ttl_hours=args.ttl_hours) if args.cmd == "claim" else lib.release(repo, args.item, args.worker)
        print(json.dumps(out, indent=1, default=str))
        return 0
    except lib.ClaimError as exc:
        print(json.dumps({"code": exc.code, "detail": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
