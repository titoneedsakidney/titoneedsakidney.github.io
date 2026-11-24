#!/usr/bin/env python3
"""Claude Code Stop hook: check the reply just finished against Tito's wording rules, WARN-ONLY (complaint audit cluster wording).

Flags (kit/hook_wording.json): 'owner' meaning Tito, a gh or ssh command handed to him, a UTC time in prose, a Tailscale instruction, and a reply
over the length limit. Code blocks and `inline code` are not checked for the prose flags (machine names like owner_asks are fine).

It NEVER blocks and prints nothing: it appends one line per reply to ~/.local/state/claude-hooks/wording.jsonl (0600, local, not in git) with the flags,
sizes and, for review, a short snippet around each match. After a week run `report` to get the false-positive review list; promotion to a blocking
check is a separate decision made with that number. Fails open. Stdlib only.

  hook_stop_wording_lint.py                      the hook (JSON on stdin: transcript_path, session_id)
  hook_stop_wording_lint.py report [--show N]    counts per flag per 100 replies, and the last N snippets to label
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = HERE / "hook_wording.json"
LOG = Path(os.environ.get("CLAUDE_WORDING_LOG") or Path.home() / ".local" / "state" / "claude-hooks" / "wording.jsonl")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")


def load_rules(path: Path = RULES) -> dict:
    return json.loads(path.read_text())


def last_assistant_text(transcript_path: str | None) -> str:
    """The text of the assistant's latest reply (all text blocks since the last typed user message)."""
    if not transcript_path:
        return ""
    parts: list[str] = []
    try:
        for line in Path(transcript_path).read_text(errors="ignore").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("isSidechain"):
                continue
            c = row.get("message", {}).get("content")
            if row.get("type") == "user":
                if isinstance(c, list) and all(isinstance(x, dict) and x.get("type") == "tool_result" for x in c):
                    continue
                parts = []  # a new typed turn starts
            elif row.get("type") == "assistant" and isinstance(c, list):
                parts += [x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"]
    except OSError:
        return ""
    return "\n".join(p for p in parts if p).strip()


def check(text: str, rules: dict) -> list[dict]:
    """Return [{flag, snippet}] and a pseudo-flag 'too_long' when over the limit."""
    prose = INLINE.sub(" ", FENCE.sub(" ", text))
    out = []
    for name, spec in rules["flags"].items():
        # a command flag looks at fenced blocks too: a shell block is exactly where a command is handed over
        haystack = text if name == "command_for_tito" else prose
        m = re.search(spec["pattern"], haystack)
        if m:
            n = rules.get("snippet_chars", 60)
            s = max(0, m.start() - n // 2)
            out.append({"flag": name, "snippet": " ".join(haystack[s:s + n].split())})
    lim = rules["length"]
    lines = [l for l in prose.splitlines() if l.strip()]
    if len(lines) > lim["max_prose_lines"] or len(text) > lim["max_chars"]:
        out.append({"flag": "too_long", "snippet": f"{len(lines)} prose lines, {len(text)} chars"})
    return out


def record(flags: list[dict], text: str, session: str = "") -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    sig = hashlib.sha1(text.encode()).hexdigest()[:12]
    try:  # a repo's settings and a user-level settings file can both register this hook: one row per reply
        last = LOG.read_text().rstrip("\n").rsplit("\n", 1)[-1] if LOG.exists() else ""
        if last and json.loads(last).get("sig") == sig and json.loads(last).get("session") == session[:8]:
            return
    except (OSError, ValueError):
        pass
    row = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "session": session[:8], "sig": sig, "chars": len(text), "flags": flags}
    fd = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(json.dumps(row) + "\n")


def report(show: int = 10, log: Path | None = None) -> dict:
    rows = []
    try:
        for line in (log or LOG).read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    counts: dict[str, int] = {}
    for r in rows:
        for f in r.get("flags", []):
            counts[f["flag"]] = counts.get(f["flag"], 0) + 1
    n = len(rows)
    recent = [dict(at=r["at"], **f) for r in rows for f in r.get("flags", []) if f["flag"] != "too_long"][-show:]
    return {"replies_checked": n, "replies_flagged": sum(1 for r in rows if r.get("flags")),
            "per_100_replies": {k: round(100 * v / n, 1) for k, v in counts.items()} if n else {}, "counts": counts, "label_these": recent,
            "how_to_judge": "A flag is a false positive when the wording was correct (for example 'owner of a thing', or a command Tito did ask for). Promote a flag to blocking only when its false positives are rare."}


def main(argv: list[str]) -> int:
    if argv[:1] == ["report"]:
        show = int(argv[argv.index("--show") + 1]) if "--show" in argv else 10
        print(json.dumps(report(show), indent=2))
        return 0
    try:
        call = json.loads(sys.stdin.read() or "{}")
        text = last_assistant_text(call.get("transcript_path"))
        if text:
            flags = check(text, load_rules())
            record(flags, text, call.get("session_id", ""))
    except Exception:  # fail open, and say nothing: warn-only
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
