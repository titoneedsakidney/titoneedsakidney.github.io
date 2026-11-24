#!/usr/bin/env python3
"""Rules self-check for one repo: are the table rules actually followed here? Offline, stdlib only, one line per check.

Part of the platform kit (source: automationpc-platform kit/rules_check.py). Run from the repo root:

  python3 platform/kit/rules_check.py [REPO_ROOT] [--remote]     exit 0 when every check passes, 1 otherwise

Checks (the worker rules they cover in brackets):
  work_list       platform/work-items.json (inventory/backlog.json in the platform) passes the common format           [1]
  stale_active    no active, agent-owned item without a claim tag on origin (needs --remote, which runs `git ls-remote`) [2]
  agents_pointer  AGENTS.md is short and points at the kit in its first lines                                           [10]
  brief           platform/BUILDER_BRIEF.md exists                                                                      [10]
  boundaries      the kit boundary list loads, and the repo's own platform/boundaries.json (if any) is valid JSON        [8]
  no_hosted       no workflow runs on a GitHub-hosted runner                                                             [6]
  release_mode    a repo with a deploy recipe says plan-only or apply in platform/release-mode.json                      [6]
  settings        .claude/settings.json exists and is a JSON object (pre-allowed ship and claim commands)               [5]
  incidents       platform/incidents/ (when it exists) passes kit/incidents.py: every incident is a sound replay case   [11]
  learning        advisory: lanes with open work and no learning, anomaly, baseline or prediction item (never fails)   [11]
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_AGENTS_LINES = 60


def _load(name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(f"kit_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_file(root: Path) -> Path:
    return root / "inventory" / "backlog.json" if (root / "inventory" / "backlog.json").exists() and not (root / "platform" / "work-items.json").exists() else root / "platform" / "work-items.json"


LEARNING = re.compile(r"learn|anomal|predict|baseline|forecast", re.I)


def lanes_without_learning(items: list) -> list[str]:
    """Lanes with open work and no item (any state but dropped) about learning, anomalies, baselines or prediction in its id or title."""
    lanes: dict[str, dict] = {}
    for i in items:
        if not isinstance(i, dict) or i.get("status") == "dropped":
            continue
        row = lanes.setdefault(i.get("lane") or "(no lane)", {"open": 0, "learning": 0})
        row["open"] += i.get("status") in ("todo", "active")
        row["learning"] += bool(LEARNING.search(str(i.get("id", "")) + " " + str(i.get("title", ""))))
    return sorted(lane for lane, row in lanes.items() if row["open"] and not row["learning"])


def claim_tags(root: Path) -> set[str] | None:
    done = subprocess.run(["git", "-C", str(root), "ls-remote", "--tags", "origin", "refs/tags/claim/backlog/*"], capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        return None
    return {line.split("refs/tags/claim/backlog/", 1)[1].rstrip("^{}") for line in done.stdout.splitlines() if "refs/tags/claim/backlog/" in line}


def run_checks(root: Path, remote: bool = False) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    data = _json(list_file(root))
    problems = _load("work_items").problems(data) if data is not None else ["list missing or not JSON"]
    out.append(("work_list", not problems, "; ".join(problems[:3]) or f"{len(data['items'])} items"))
    if remote and isinstance(data, dict):
        tags = claim_tags(root)
        if tags is None:
            out.append(("stale_active", False, "could not read claim tags from origin"))
        else:
            stale = sorted(i["id"] for i in data.get("items", []) if i.get("status") == "active" and i.get("owner") not in ("tito", "owner")
                           and not i.get("ask") and i["id"] not in tags)
            out.append(("stale_active", not stale, ", ".join(stale[:8]) + (f" (+{len(stale) - 8})" if len(stale) > 8 else "") if stale else "none"))
    agents = (root / "AGENTS.md").read_text(encoding="utf-8").splitlines() if (root / "AGENTS.md").exists() else None
    if agents is None:
        out.append(("agents_pointer", False, "no AGENTS.md"))
    else:
        pointer = any("kit" in line.lower() for line in agents[:10])
        out.append(("agents_pointer", pointer and len(agents) <= MAX_AGENTS_LINES, f"{len(agents)} lines, kit pointer {'yes' if pointer else 'missing'}"))
    out.append(("brief", (root / "platform" / "BUILDER_BRIEF.md").exists(), "platform/BUILDER_BRIEF.md"))
    kit_boundaries = _json(HERE / "boundaries.json")
    own = root / "platform" / "boundaries.json"
    out.append(("boundaries", isinstance(kit_boundaries, dict) and (not own.exists() or isinstance(_json(own), dict)), "kit list and repo list load"))
    hosted = _load("no_hosted_runners").check_repo(root)
    out.append(("no_hosted", hosted["ok"], f"{hosted['workflows']} workflows" if hosted["ok"] else f"{len(hosted['problems'])} problems"))
    if (root / "platform" / "deploy-recipe.json").exists():
        release = _json(root / "platform" / "release-mode.json")
        mode = release.get("mode") if isinstance(release, dict) else None
        out.append(("release_mode", mode in ("plan-only", "apply"), f"mode {mode!r}"))
    settings = _json(root / ".claude" / "settings.json")
    out.append(("settings", isinstance(settings, dict), ".claude/settings.json"))
    found = _load("incidents").problems(root)
    out.append(("incidents", not found, "; ".join(found[:2]) + (f" (+{len(found) - 2})" if len(found) > 2 else "") if found else "ok or none recorded"))
    gaps = lanes_without_learning((data or {}).get("items", []) if isinstance(data, dict) else [])
    out.append(("learning", True, ("advisory: no learning roadmap in lane " + ", ".join(gaps[:6])) if gaps else "every lane has a learning roadmap item"))
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    remote = "--remote" in args
    rest = [a for a in args if not a.startswith("--")]
    root = Path(rest[0] if rest else ".").resolve()
    results = run_checks(root, remote)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:15} {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
