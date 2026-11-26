#!/usr/bin/env python3
"""Incident replay library check (platform kit; source: automationpc-platform kit/incidents.py). Stdlib only.

  python3 platform/kit/incidents.py check [REPO_ROOT]   exit 1 and name each problem; exit 0 when the library is sound (or absent)
  python3 platform/kit/incidents.py list [REPO_ROOT]    one line per incident: id, status, item

An incident (format: incident.schema.json) is something a person noticed before the system did. Each one is a replay case for the
repo's detector. Owner rule 2026-10-17: a targeted fix is never the whole job; the incident is recorded, the general detector is checked
against it, a guard shipped meanwhile is a labelled seatbelt, and the incident stays open on a roadmap item until the detector catches it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STATUSES = ("none", "seatbelt_only", "caught_after_the_fact", "caught_in_time")
KINDS = ("context_surprise", "command_not_followed", "service_failure", "radio", "energy", "other")
REQUIRED = ("id", "date", "what", "signals", "window", "should_flag", "expected_kind", "detector_status")
ID = re.compile(r"^INC-\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")


def folder(root: Path) -> Path:
    return root / "platform" / "incidents"


def load(root: Path):
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(folder(root).glob("INC-*.json"))]


def item_ids(root: Path) -> set[str]:
    for candidate in (root / "platform" / "work-items.json", root / "inventory" / "backlog.json"):
        if candidate.exists():
            try:
                return {i["id"] for i in json.loads(candidate.read_text(encoding="utf-8")).get("items", []) if isinstance(i, dict)}
            except (OSError, ValueError):
                return set()
    return set()


def problems(root: Path) -> list[str]:
    out: list[str] = []
    if not folder(root).exists():
        return out
    ids = item_ids(root)
    try:
        incidents = load(root)
    except ValueError as exc:
        return [f"an incident file is not JSON: {exc}"]
    for path, inc in incidents:
        name = path.stem
        missing = [k for k in REQUIRED if k not in inc]
        if missing:
            out.append(f"{name}: missing {', '.join(missing)}")
            continue
        if inc["id"] != name or not ID.match(name):
            out.append(f"{name}: id must equal the file name and look like INC-YYYY-MM-DD-slug")
        window = inc["window"]
        if not (isinstance(window, dict) and window.get("start") and window.get("end") and window["start"] < window["end"]):
            out.append(f"{name}: window needs start before end")
        if not isinstance(inc["should_flag"], bool):
            out.append(f"{name}: should_flag must be true or false")
        if inc["expected_kind"] not in KINDS:
            out.append(f"{name}: expected_kind {inc['expected_kind']!r} is not one of {', '.join(KINDS)}")
        if inc["detector_status"] not in STATUSES:
            out.append(f"{name}: detector_status {inc['detector_status']!r} is not one of {', '.join(STATUSES)}")
            continue
        if not inc["signals"]:
            out.append(f"{name}: name the signals where the evidence lives")
        if inc["detector_status"] in ("none", "seatbelt_only") and not inc.get("seatbelt"):
            out.append(f"{name}: say what stops it recurring meanwhile (seatbelt)")
        if inc["detector_status"] != "caught_in_time" and inc.get("item") not in ids:
            out.append(f"{name}: item {inc.get('item')!r} is not on this repo's work list; track the detector work there")
    return out


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "check"
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if cmd == "list":
        for _path, inc in load(root):
            print(f"{inc.get('id')}  {inc.get('detector_status')}  {inc.get('item', '-')}")
        return 0
    found = problems(root)
    print(json.dumps({"ok": not found, "incidents": len(load(root)) if folder(root).exists() else 0, "problems": found}, indent=1))
    return 0 if not found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
