#!/usr/bin/env python3
"""Claude Code PreToolUse hook: deny three costly mistakes the complaint audit found (docs/architecture/complaint-audit-2026-10-24.json).

Rules live in kit/hook_guards.json (delivered to platform/kit/ in every repo):
  ha_night     a ship or merge command for a change under homeassistant/ between 22:00 and 07:00 America/New_York (2026-10-24 restart woke Tito)
  agent_spawn  an Agent/Task call when Tito's latest message did not ask for agents, parallel work or a workflow (subagents burned the usage window)
  pkill_f      `pkill -f` / `pgrep -f` in a Bash call without the [x] trick (matches its own shell)

The hook reads the tool call as JSON on stdin and answers with a deny decision, or says nothing (allow). It FAILS OPEN: any error allows the call.
It never changes a command, reads no secrets, and logs only the rule name, tool and time (no command text) to ~/.local/state/claude-hooks/guards.log.
Stdlib only.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
RULES = HERE / "hook_guards.json"
LOG = Path(os.environ.get("CLAUDE_GUARD_LOG") or Path.home() / ".local" / "state" / "claude-hooks" / "guards.log")


def load_rules(path: Path = RULES) -> dict:
    return json.loads(path.read_text())


def in_hold_window(now: dt.datetime, start: str, end: str) -> bool:
    s = dt.time.fromisoformat(start)
    e = dt.time.fromisoformat(end)
    t = now.time()
    return t >= s or t < e if s > e else s <= t < e


def last_user_text(transcript_path: str | None) -> str:
    """Tito's latest typed message from the session transcript (JSONL). Empty when it cannot be read."""
    if not transcript_path:
        return ""
    try:
        text = ""
        for line in Path(transcript_path).read_text(errors="ignore").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") != "user" or row.get("isSidechain"):
                continue
            c = row.get("message", {}).get("content")
            if isinstance(c, list):
                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
            if isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
                text = c
        return text
    except OSError:
        return ""


def changed_files(command: str, cwd: str) -> list[str]:
    """Files the shipped change touches: the worktree given to ship_pr.sh, or the PR given to gh pr merge. Empty when unknown (fail open)."""
    try:
        m = re.search(r"ship_pr\.sh\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))", command)
        if m:
            wt = os.path.expanduser(m.group(1) or m.group(2) or m.group(3))
            out = subprocess.run(["git", "-C", wt, "diff", "--name-only", "origin/main"], capture_output=True, text=True, timeout=8).stdout
            out += subprocess.run(["git", "-C", wt, "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True, timeout=8).stdout
            return out.split()
        m = re.search(r"gh\s+pr\s+merge\s+(\d+)", command)
        if m:
            env = dict(os.environ, GH_CONFIG_DIR=os.environ.get("GH_CONFIG_DIR") or str(Path.home() / ".config" / "gh-agent"))
            return subprocess.run(["gh", "pr", "diff", m.group(1), "--name-only"], capture_output=True, text=True, timeout=10, cwd=cwd or None, env=env).stdout.split()
    except (OSError, subprocess.SubprocessError):
        pass
    return []


def decide(call: dict, rules: dict, now: dt.datetime | None = None, files_for=changed_files, user_text_for=last_user_text) -> tuple[str, str] | None:
    """Return (rule, reason) to deny, or None to allow."""
    tool = call.get("tool_name") or ""
    inp = call.get("tool_input") or {}
    cmd = inp.get("command", "") if tool == "Bash" else ""

    if tool in rules["agent_spawn"]["tools"]:
        asked = user_text_for(call.get("transcript_path")).lower()
        if not any(w in asked for w in rules["agent_spawn"]["asked_words"]):
            return "agent_spawn", rules["agent_spawn"]["reason"]

    if tool == "Bash" and re.search(r"\b(pkill|pgrep)\b[^|;&\n]*?\s(-\w*f\w*|--full)\b", cmd):
        if not re.search(r"\[[A-Za-z0-9_.\-]\]", cmd):
            return "pkill_f", rules["pkill_f"]["reason"]

    if tool == "Bash":
        r = rules["ha_night"]
        if any(s in cmd for s in r["ship_commands"]) and "CLAUDE_GUARD_ALLOW=ha-night" not in cmd:
            tz = ZoneInfo(rules.get("timezone", "America/New_York"))
            local = (now or dt.datetime.now(tz)).astimezone(tz)
            if in_hold_window(local, r["hold_from"], r["hold_until"]) and "nomerge" not in cmd:
                if any(f.startswith(tuple(r["ha_path_prefixes"])) for f in files_for(cmd, call.get("cwd") or "")):
                    return "ha_night", r["reason"]
    return None


def log(rule: str, tool: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        if LOG.exists():  # both a repo's and a user-level registration may run: one line per denial
            last = json.loads(LOG.read_text().rstrip("\n").rsplit("\n", 1)[-1])
            when = dt.datetime.strptime(last["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            if last.get("rule") == rule and last.get("tool") == tool and (dt.datetime.now(dt.timezone.utc) - when).total_seconds() < 3:
                return
        with LOG.open("a") as fh:
            fh.write(json.dumps({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rule": rule, "tool": tool}) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        call = json.loads(sys.stdin.read() or "{}")
        verdict = decide(call, load_rules())
    except Exception:  # fail open: a broken guard never blocks work
        return 0
    if verdict:
        rule, reason = verdict
        log(rule, call.get("tool_name", ""))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": f"[guard:{rule}] {reason}"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
