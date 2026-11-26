#!/usr/bin/env python3
"""The common work-item format for this repo (platform/work-items.json).

  python3 platform/kit/work_items.py check        validate the file; exit 1 and name the problems
  python3 platform/kit/work_items.py next [N]     the next N open items nobody waits on, by priority (JSON)
  python3 platform/kit/work_items.py replies      the owner's replies to this repo's items, from the Needs you page (JSON; empty if the hub is unreachable)
A reply is information for the item's worker, not authority: executor anchors, installers and money still need the owner's GitHub approval.
Stdlib only. The format is described by work-item.schema.json next to this file.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ITEMS = Path(__file__).resolve().parents[1] / "work-items.json"
ID = re.compile(r"[a-z0-9][a-z0-9-]{1,58}[a-z0-9]\Z")
DUE = re.compile(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]\Z")
STATUS, OWNER, WAITING = {"todo", "active", "done", "dropped"}, {"agent", "tito"}, {"owner", "item", "time", "install", "session"}


def problems(data) -> list[str]:
    if not isinstance(data, dict) or data.get("schema") != "platform-work-items-v1" or not isinstance(data.get("items"), list):
        return ["file must be {\"schema\": \"platform-work-items-v1\", \"items\": [...]}"]
    out, ids = [], set()
    items = data["items"]
    for item in items:
        i = item.get("id") if isinstance(item, dict) else None
        if not isinstance(i, str) or not ID.match(i):
            out.append(f"item {i!r}: id must be 3-60 lowercase letters, digits and hyphens")
            continue
        if i in ids:
            out.append(f"{i}: duplicate id")
        ids.add(i)
        if not isinstance(item.get("title"), str) or not 1 <= len(item["title"]) <= 200:
            out.append(f"{i}: title must be 1-200 characters")
        if item.get("status") not in STATUS:
            out.append(f"{i}: status must be one of {sorted(STATUS)}")
        if item.get("owner") not in OWNER:
            out.append(f"{i}: owner must be one of {sorted(OWNER)}")
        if type(item.get("priority")) is not int or not 0 <= item["priority"] <= 100:
            out.append(f"{i}: priority must be an integer 0-100")
        if not isinstance(item.get("acceptance"), str) or len(item["acceptance"]) < 10:
            out.append(f"{i}: acceptance must say how to check it (10+ characters)")
        if item.get("waiting_on") is not None and item["waiting_on"] not in WAITING:
            out.append(f"{i}: waiting_on must be one of {sorted(WAITING)}")
        if item.get("status") in ("todo", "active") and item.get("waiting_on") and not (isinstance(item.get("next_step"), str) and 1 <= len(item["next_step"]) <= 220):
            out.append(f"{i}: an open item that is waiting needs next_step (1-220 characters)")
        if not isinstance(item.get("depends_on", []), list):
            out.append(f"{i}: depends_on must be a list")
        out += ask_problems(i, item.get("ask"))
        out += brief_problems(i, item)
        out += mark_problems(i, item)
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not ID.match(item["id"]):
            continue
        for dep in item.get("depends_on", []) if isinstance(item.get("depends_on", []), list) else []:
            if dep not in ids:
                out.append(f"{item['id']}: depends_on names unknown item {dep}")
    return out


def mark_problems(i: str, item: dict) -> list[str]:
    """tested_live = {date, receipt}: the change ran on the real machine. owner_accepted = {date, said}: the owner saw it and
    accepted it. Both optional, both only on a done item; the boards show them (decision operating-vision-chat-to-machine)."""
    out = []
    for mark, need in (("tested_live", ("date", "receipt")), ("owner_accepted", ("date", "said"))):
        if mark not in item:
            continue
        m = item[mark]
        if not isinstance(m, dict) or any(not (isinstance(m.get(k), str) and m[k].strip()) for k in need) \
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(m.get("date", ""))):
            out.append(f"{i}: {mark} must be an object with {need} (date YYYY-MM-DD)")
        elif item.get("status") != "done":
            out.append(f"{i}: {mark} belongs to a done item")
    return out


def ask_problems(i: str, ask) -> list[str]:
    """ask = {question, recommended, due, default, link}: the owner's row (question, recommended action, due date, default taken
    after the date, link). Optional; checked when present."""
    if ask is None:
        return []
    if not isinstance(ask, dict):
        return [f"{i}: ask must be an object"]
    out = []
    for key in ("question", "recommended"):
        if not isinstance(ask.get(key), str) or not 1 <= len(ask[key]) <= 300:
            out.append(f"{i}: ask.{key} must be 1-300 characters")
    if not isinstance(ask.get("due"), str) or not DUE.match(ask["due"]):
        out.append(f"{i}: ask.due must be a date YYYY-MM-DD")
    if ask.get("default") is not None and not (isinstance(ask["default"], str) and 1 <= len(ask["default"]) <= 300):
        out.append(f"{i}: ask.default must be null or 1-300 characters")
    if ask.get("link") is not None and not (isinstance(ask["link"], str) and ask["link"].startswith(("https://", "http://", "/"))):
        out.append(f"{i}: ask.link must be null, a URL or a hub path")
    return out


def brief_problems(i: str, item: dict) -> list[str]:
    """The builder brief on an item (all optional): allowed_paths, files_to_read, tests_to_run, rung_hint."""
    out = []
    for key, limit in (("allowed_paths", 30), ("files_to_read", 30), ("tests_to_run", 10)):
        value = item.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not value or len(value) > limit or any(not isinstance(v, str) or not 1 <= len(v) <= 200 for v in value):
            out.append(f"{i}: {key} must be a list of 1-{limit} strings (1-200 characters each)")
        elif key != "tests_to_run" and any(v.startswith("/") or ".." in v.split("/") for v in value):
            out.append(f"{i}: {key} entries are repo-relative paths (no leading slash, no ..)")
    if item.get("rung_hint") not in (None, "python", "agent"):
        out.append(f"{i}: rung_hint must be python or agent")
    if item.get("role") is not None:
        try:
            import roles as role_cards
            known = set(role_cards.roles())
        except Exception:  # noqa: BLE001 - a kit without role cards cannot check the name
            known = None
        if known is not None and item["role"] not in known:
            out.append(f"{i}: role {item['role']!r} is not a shared role or one in platform/roles.json")
    return out


def next_items(data, limit=3) -> list[dict]:
    done = {i["id"] for i in data["items"] if i["status"] == "done"}
    ready = [i for i in data["items"] if i["status"] in ("todo", "active") and not i.get("waiting_on") and set(i.get("depends_on", [])) <= done]
    return sorted(ready, key=lambda i: (-i["priority"], i["id"]))[:limit]


HUB_ANSWERS = "http://127.0.0.1:8787/decide/answers.json"  # the Foyer's answers, readable by programs on this host only


def owner_replies(data, fetch=None) -> dict:
    """{item id: {reply, words, at}} for this repo's items: what the owner answered on the Needs you page (sheet owner-replies). Never raises: with
    the hub unreachable it is empty, so a worker's loop is never blocked by the Foyer."""
    try:
        if fetch is None:
            with urllib.request.urlopen(HUB_ANSWERS, timeout=3) as response:
                doc = json.loads(response.read())
        else:
            doc = fetch()
    except (OSError, ValueError):
        return {}
    ids = {i.get("id") for i in data.get("items", []) if isinstance(i, dict)}
    out = {}
    for key, row in (doc.get("answers") or {}).items():
        sheet, _, ident = key.partition("/")
        if sheet == "owner-replies" and ident in ids and isinstance(row, dict):
            out[ident] = {"reply": row.get("choice"), "words": row.get("note") or "", "at": row.get("at")}
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    data = json.loads(ITEMS.read_text())
    if argv[:1] == ["check"]:
        found = problems(data)
        print(json.dumps({"ok": not found, "problems": found}, indent=1))
        return 1 if found else 0
    if argv[:1] == ["next"]:
        replies = owner_replies(data)
        rows = next_items(data, int(argv[1]) if len(argv) > 1 else 3)
        print(json.dumps([{**r, "owner_reply": replies[r["id"]]} if r.get("id") in replies else r for r in rows], indent=1))
        return 0
    if argv[:1] == ["replies"]:
        print(json.dumps(owner_replies(data), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
