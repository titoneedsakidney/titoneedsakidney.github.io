#!/usr/bin/env python3
"""The table-rules check for a pull request (worker rules 1 and 3). Run in CI on pull_request events:

  python3 platform/kit/check_pr.py            reads $GITHUB_EVENT_PATH; exit 0 when this is not a pull request
  python3 platform/kit/check_pr.py --body-file FILE [--branch NAME]   for local use and tests

Passes when the PR body carries a line `item: <id>` and that id is on this repo's work list
(platform/work-items.json, or inventory/backlog.json in the platform repo), or the line is `item: platform:<id>`
for an item that lives on the platform's backlog. The kit's own sync branches (platform/kit-*) pass. Stdlib only.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if Path(__file__).resolve().parent.name == "kit" and Path(__file__).resolve().parents[1].name == "platform" \
    else Path(__file__).resolve().parents[1]
ITEM = re.compile(r"^item:\s*(platform:)?([a-z0-9][a-z0-9-]{1,58}[a-z0-9])\s*$", re.M)
LISTS = ("platform/work-items.json", "inventory/backlog.json")


def local_ids(root: Path = ROOT) -> set:
    ids = set()
    for rel in LISTS:
        try:
            ids |= {i.get("id") for i in json.loads((root / rel).read_text()).get("items", []) if isinstance(i, dict)}
        except (OSError, ValueError):
            continue
    return ids


def problems(body: str, branch: str = "", ids: set | None = None) -> list:
    if branch.startswith("platform/kit-"):
        return []
    found = ITEM.findall(body or "")
    if not found:
        return ["the pull request body has no `item: <id>` line (worker rule 3); add the work item's id as the last line"]
    ids = local_ids() if ids is None else ids
    for prefix, item in found:
        if prefix or item in ids:
            return []
    named = ", ".join(i for _, i in found)
    return [f"item {named} is not on this repo's work list; add it to platform/work-items.json in this PR, "
            "or write `item: platform:<id>` if it is a platform backlog item"]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    branch = ""
    if "--body-file" in argv:
        body = Path(argv[argv.index("--body-file") + 1]).read_text()
        if "--branch" in argv:
            branch = argv[argv.index("--branch") + 1]
    else:
        path = os.environ.get("GITHUB_EVENT_PATH")
        if not path or not Path(path).is_file():
            print(json.dumps({"ok": True, "skipped": "not a GitHub event"}))
            return 0
        event = json.loads(Path(path).read_text())
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            print(json.dumps({"ok": True, "skipped": "not a pull request"}))
            return 0
        body, branch = pr.get("body") or "", (pr.get("head") or {}).get("ref") or ""
    found = problems(body, branch)
    print(json.dumps({"ok": not found, "problems": found}, indent=1))
    for line in found:
        print(f"::error title=TABLE_RULES::{line}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
