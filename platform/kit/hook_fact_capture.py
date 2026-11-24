#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: when Tito states a fact or corrects a repeat, tell the session to record it NOW (audit cluster stated-fact-did-not-stick:
the 20 USD audit and the LAN address were each stated three or four times and lost, because nothing turned a chat statement into a record at the first statement).

Reads the prompt (JSON on stdin), matches it against the phrases in kit/hook_fact_phrases.json and, on a match, prints one line of context (Claude Code adds a
UserPromptSubmit hook's stdout to the turn). It also appends the matched phrase and the time, NOT the prompt, to ~/.local/state/claude-hooks/facts-inbox.jsonl
(0600, local) so repeats can be counted. It never blocks, prints nothing for an ordinary prompt, and fails open. Registered at repo level and user level, so a repeat
call for the same prompt is a no-op. Stdlib only.

  hook_fact_capture.py            the hook
  hook_fact_capture.py report     phrase counts from the inbox (counts only)
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
PHRASES = HERE / "hook_fact_phrases.json"
INBOX = Path(os.environ.get("CLAUDE_FACTS_INBOX") or Path.home() / ".local" / "state" / "claude-hooks" / "facts-inbox.jsonl")


def load(path: Path = PHRASES) -> dict:
    return json.loads(path.read_text())


def match(prompt: str, rules: dict) -> str | None:
    """The matched phrase of the first pattern that fits, else None. Pasted blocks and quoted system text are not Tito's words."""
    text = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", " ", prompt or "", flags=re.S | re.I)
    text = re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.S)
    for pat in rules["patterns"]:
        m = re.search(pat, text, re.I)
        if m:
            return " ".join(m.group(0).split())[:60]
    return None


def record(phrase: str, session: str, sig: str, inbox: Path | None = None) -> bool:
    """Append one row; False when the same prompt was already recorded for this session (a repo-level and a user-level registration may both run)."""
    inbox = inbox or INBOX
    inbox.parent.mkdir(parents=True, exist_ok=True)
    try:
        if inbox.exists():
            last = json.loads(inbox.read_text().rstrip("\n").rsplit("\n", 1)[-1])
            if last.get("sig") == sig and last.get("session") == session[:8]:
                return False
    except (OSError, ValueError):
        pass
    row = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "session": session[:8], "sig": sig, "phrase": phrase}
    fd = os.open(inbox, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(json.dumps(row) + "\n")
    return True


def report(inbox: Path | None = None) -> dict:
    counts: dict[str, int] = {}
    total = 0
    try:
        for line in (inbox or INBOX).read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            total += 1
            counts[row.get("phrase", "?")] = counts.get(row.get("phrase", "?"), 0) + 1
    except OSError:
        pass
    return {"prompts_flagged": total, "by_phrase": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}


def main(argv: list[str]) -> int:
    if argv[:1] == ["report"]:
        print(json.dumps(report(), indent=2))
        return 0
    try:
        call = json.loads(sys.stdin.read() or "{}")
        prompt = call.get("prompt") or ""
        rules = load()
        phrase = match(prompt, rules)
        if phrase:
            sig = hashlib.sha1(prompt.encode()).hexdigest()[:12]
            first = record(phrase, str(call.get("session_id") or ""), sig)
            if first:
                print(rules["nudge"].format(phrase=phrase))
    except Exception:  # fail open, silently
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
