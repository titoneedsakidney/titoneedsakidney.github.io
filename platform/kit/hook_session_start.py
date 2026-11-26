#!/usr/bin/env python3
"""Claude Code SessionStart hook: put the written record in front of the session before it acts (audit docs/architecture/complaint-audit-2026-10-24.json,
cluster forgot-the-record: decisions and rules existed but were not read, and a compaction drops what was loaded).

Registered in .claude/settings.json for startup, resume, clear and compact. Claude Code adds this script's stdout to the session's context.
Prints, in at most MAX_CHARS: the standing facts Tito has stated (in full, first, so they are never the part that is cut), the repo's first steps, the newest decision records, the next work item, and a pointer to the skills.
Fails open: any error prints one short line and exits 0, so a broken hook never blocks a session. Reads files and one local command; no network,
no private data, nothing is written. Stdlib only.

  hook_session_start.py [--root DIR] [--source startup|resume|clear|compact]      (the hook also passes its JSON on stdin; --source overrides it)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_CHARS = 6500
NEWEST_DECISIONS = 4
# The decisions and first steps live in the platform repo. A product repo carries this hook in platform/kit/ and reads them from the platform checkout on
# this host (PLATFORM_REPO overrides the path); if that checkout is missing the hook still prints what the repo itself holds.
PLATFORM_REPO = Path(os.environ.get("PLATFORM_REPO") or Path.home() / "automationpc-platform")


def _trim(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def record_root(root: Path) -> Path | None:
    """Where the written record is: this repo when it holds docs/decisions (the platform repo), else the platform checkout on this host."""
    for cand in (root, PLATFORM_REPO):
        if (cand / "docs" / "decisions").is_dir():
            return cand
    return None


def standing_facts(root: Path) -> list[str]:
    """Every fact Tito has stated that changes how a number, link or message is produced (docs/standing-facts.json), in full: a standing
    fact must not depend on a memory note being recalled or on being among the newest decisions."""
    base = record_root(root)
    try:
        facts = json.loads((base / "docs" / "standing-facts.json").read_text()).get("facts") or [] if base else []
        return [_trim(f["statement"], 260) for f in facts if isinstance(f, dict) and f.get("statement")]
    except (OSError, ValueError):
        return []


def first_steps(root: Path) -> list[str]:
    base = record_root(root)
    try:
        steps = json.loads((base / "docs" / "START_HERE.json").read_text()).get("first_steps") or [] if base else []
        return [_trim(s, 230) for s in steps[:8]]
    except (OSError, ValueError):
        return []


def newest_decisions(root: Path, limit: int = NEWEST_DECISIONS) -> list[str]:
    out = []
    base = record_root(root)
    for p in (sorted((base / "docs" / "decisions").glob("20*.json"), reverse=True)[:limit] if base else []):
        try:
            d = json.loads(p.read_text())
            out.append(f"{d.get('decided', p.name[:10])} {d.get('id', p.stem)}: {_trim(d.get('decision', ''), 170)}")
        except (OSError, ValueError):
            out.append(p.stem)
    return out


def next_items(root: Path, limit: int = 2) -> list[str]:
    for argv in (["python3", "tools/backlog.py", "next", "--limit", str(limit)], ["python3", "platform/kit/work_items.py", "next"], ["python3", "kit/work_items.py", "next"]):
        if not (root / argv[1]).exists():
            continue
        try:
            res = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=10)
            data = json.loads(res.stdout)
            items = data if isinstance(data, list) else data.get("next") or data.get("items") or []
            return [f"{i.get('id')}: {_trim(i.get('title', ''), 140)}" for i in items[:limit] if isinstance(i, dict)]
        except (OSError, ValueError, subprocess.SubprocessError):
            return []
    return []


def skills(root: Path) -> list[str]:
    try:
        return sorted(p.parent.name for p in (root / ".claude" / "skills").glob("*/SKILL.md"))
    except OSError:
        return []


def build(root: Path, source: str) -> str:
    lines = ["THE RECORD (read before acting; the repo is the record, memory and chat summaries are not)."]
    if source == "compact":
        lines.append("Context was just compacted: whatever you held about decisions and rules is gone. Re-read the items below and docs/decisions/INDEX.md before the next action.")
    facts = standing_facts(root)
    if facts:
        lines += ["", "Standing facts Tito has stated (docs/standing-facts.json; do not ask again, do not recompute them differently):"] + [f"- {f}" for f in facts]
    steps = first_steps(root)
    if steps:
        lines += ["", "First steps:"] + [f"- {s}" for s in steps]
    decisions = newest_decisions(root)
    if decisions:
        lines += ["", "Newest decisions (docs/decisions/, a decision outranks your memory):"] + [f"- {d}" for d in decisions]
    nxt = next_items(root)
    if nxt:
        lines += ["", "Next work item (claim it before starting; work not on the list gets an item first):"] + [f"- {n}" for n in nxt]
    names = skills(root)
    if names:
        lines += ["", "Repo skills that load for matching work: " + ", ".join(names) + "."]
    if (root / "AGENTS.md").exists() and not (root / "docs" / "decisions").is_dir():
        lines += ["", "This repo: read AGENTS.md, platform/BUILDER_BRIEF.md and platform/kit/WORKER_RULES.md before work; the decisions above are the platform's and bind you here too."]
    lines += ["", "Say Tito, not owner. Times in America/New_York. Never hand Tito a gh or ssh command; look for the executor route first."]
    text = "\n".join(lines)
    return text if len(text) <= MAX_CHARS else text[: MAX_CHARS - 1].rstrip() + "…"


def already_ran(session_id: str, source: str, tmp: Path | None = None) -> bool:
    """True when this hook already ran for this session start. A repo's own settings and a user-level settings file can both register it; the
    first run prints the record and the second prints nothing (an atomic marker file, so two processes cannot both win)."""
    if not session_id:
        return False
    marker = (tmp or Path(tempfile.gettempdir())) / f"claude-record-{hashlib.sha1(f'{session_id}:{source}'.encode()).hexdigest()[:16]}"
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return False
    except FileExistsError:
        return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root")
    ap.add_argument("--source")
    args = ap.parse_args(argv)
    try:
        source, session_id = args.source, ""
        if source is None and not sys.stdin.isatty():
            try:
                payload = json.loads(sys.stdin.read() or "{}") or {}
                source, session_id = payload.get("source", "startup"), str(payload.get("session_id") or "")
            except ValueError:
                source = "startup"
        if already_ran(session_id, source or "startup"):
            return 0
        root = Path(args.root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        print(build(root, source or "startup"))
    except Exception as exc:  # fail open: never block a session
        print(f"(record hook skipped: {type(exc).__name__}; read docs/START_HERE.md and docs/decisions/ yourself)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
