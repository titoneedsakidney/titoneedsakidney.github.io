#!/usr/bin/env python3
"""The boundary check: is this change on THE list of real boundaries (boundaries.json)?

  python3 platform/kit/boundary.py list                         the rules, one line each
  python3 platform/kit/boundary.py check --diff FILE            a unified diff (git diff base...head)
  python3 platform/kit/boundary.py check --pr                   in CI: the pull request's files through the GitHub API
  python3 platform/kit/boundary.py capability NAME              exit 3 when NAME (e.g. email.send) is a boundary

Exit 0 = no boundary; 3 = boundary hit (the JSON says which rule and where). Nobody decides what a boundary is at run
time: the list is data, kept in the platform (kit/boundaries.json) and extended per repo in platform/boundaries.json.
Stdlib only.
"""
import fnmatch
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = HERE.parent / "boundaries.json"   # platform/boundaries.json in a product repo: adds rules, never removes


def rules() -> list:
    out = list(json.loads((HERE / "boundaries.json").read_text())["rules"])
    if LOCAL.is_file() and LOCAL.resolve() != (HERE / "boundaries.json").resolve():
        try:
            out += [r for r in json.loads(LOCAL.read_text()).get("rules", []) if isinstance(r, dict) and r.get("id")]
        except ValueError:
            out.append({"id": "local-list-unreadable", "what": "platform/boundaries.json is not valid JSON", "paths": ["*"], "added_lines": []})
    return out


def parse_diff(text: str) -> dict:
    """path -> list of added lines, from a unified diff."""
    files, current = {}, None
    for line in text.splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            current = None if name == "/dev/null" else (name[2:] if name.startswith("b/") else name)
            if current is not None:
                files.setdefault(current, [])
        elif line.startswith("--- ") and line[4:].strip() != "/dev/null":
            name = line[4:].strip()
            files.setdefault(name[2:] if name.startswith("a/") else name, [])  # deleted or changed file still counts as touched
        elif line.startswith("+") and current is not None:
            files[current].append(line[1:])
    return files


def hits(files: dict, rule_list: list | None = None) -> list:
    out = []
    for rule in rules() if rule_list is None else rule_list:
        for path, added in sorted(files.items()):
            if any(fnmatch.fnmatch(path, pattern) for pattern in rule.get("paths", [])):
                out.append({"rule": rule["id"], "path": path, "why": "path is on the boundary list"})
                continue
            for pattern in rule.get("added_lines", []):
                if any(re.search(pattern, line) for line in added):
                    out.append({"rule": rule["id"], "path": path, "why": "an added line matches a boundary pattern"})  # never echo the line
                    break
    return out


def pr_files() -> dict:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        return {}
    repo, number, token = event["repository"]["full_name"], pr["number"], os.environ.get("GITHUB_TOKEN", "")
    files, page = {}, 1
    while True:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/pulls/{number}/files?per_page=100&page={page}",
                                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "platform-kit"})
        with urllib.request.urlopen(req, timeout=30) as response:
            rows = json.loads(response.read())
        for row in rows:
            patch = row.get("patch") or ""
            files[row["filename"]] = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
        if len(rows) < 100:
            break
        page += 1
    return files


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["list"]:
        for rule in rules():
            print(f"{rule['id']}: {rule['what']}")
        return 0
    if argv[:1] == ["capability"] and len(argv) == 2:
        found = [r["id"] for r in rules() if argv[1] in r.get("capabilities", [])]
        print(json.dumps({"capability": argv[1], "boundary": bool(found), "rules": found}))
        return 3 if found else 0
    if argv[:1] == ["check"]:
        if "--diff" in argv:
            files = parse_diff(Path(argv[argv.index("--diff") + 1]).read_text(errors="replace"))
        elif "--pr" in argv:
            if not os.environ.get("GITHUB_EVENT_PATH"):
                print(json.dumps({"boundary": False, "skipped": "not a GitHub event"}))
                return 0
            files = pr_files()
        else:
            print(__doc__)
            return 2
        found = hits(files)
        print(json.dumps({"boundary": bool(found), "hits": found}, indent=1))
        for h in found:
            print(f"::warning title=BOUNDARY {h['rule']}::{h['path']}: {h['why']}. This change needs the owner (an ask on the work item).")
        return 3 if found else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
