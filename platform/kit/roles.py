#!/usr/bin/env python3
"""Role cards (roles.json here, plus this repo's platform/roles.json).

  python3 platform/kit/roles.py list            every role, one line each
  python3 platform/kit/roles.py card ROLE       the card as JSON (what a job gives the model with the item)
  python3 platform/kit/roles.py resolve '{"kind": "fix"}'   which role an item needs (its role, else its kind through work-types.json)
  python3 platform/kit/roles.py check           the repo's own roles file is well formed and redefines no shared role

Stdlib only. Shared roles are edited in the platform (kit/roles.json), product roles in the product repo.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = HERE.parent / "roles.json"
FIELDS = ("id", "does", "reads", "may_change", "hands_back", "stops_when")
ID = re.compile(r"[a-z][a-z0-9-]{1,38}[a-z0-9]\Z")
DEFAULT = "builder"


def shared() -> list:
    return json.loads((HERE / "roles.json").read_text())["roles"]


def local_problems(path: Path = LOCAL) -> list:
    if not path.is_file() or path.resolve() == (HERE / "roles.json").resolve():
        return []
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return ["platform/roles.json is not valid JSON"]
    rows = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return ["platform/roles.json must be {\"roles\": [...]}"]
    out, taken = [], {r["id"] for r in shared()}
    for row in rows:
        rid = row.get("id") if isinstance(row, dict) else None
        if not isinstance(rid, str) or not ID.match(rid):
            out.append(f"role {rid!r}: id must be 3-40 lowercase letters, digits and hyphens")
            continue
        if rid in taken:
            out.append(f"role {rid}: already defined (shared roles cannot be redefined; pick another id)")
        taken.add(rid)
        for field in FIELDS[1:]:
            if not isinstance(row.get(field), str) or not 3 <= len(row[field]) <= 400:
                out.append(f"role {rid}: {field} must be 3-400 characters")
    return out


def roles() -> dict:
    out = {r["id"]: dict(r, source="shared") for r in shared()}
    if LOCAL.is_file() and LOCAL.resolve() != (HERE / "roles.json").resolve() and not local_problems():
        for row in json.loads(LOCAL.read_text())["roles"]:
            out[row["id"]] = dict(row, source="product")
    return out


def work_types() -> dict:
    return json.loads((HERE / "work-types.json").read_text())


def resolve(item: dict) -> dict:
    """Which worker an item needs, from data only: {"role": id or None, "how": item|kind|person|needs_label, "detail": why}. The model never decides this.
    Order: the item's own role (a shared or product role), then its kind through work-types.json, then 'person' kinds, else the planner must label it."""
    known = roles()
    own = item.get("role")
    if own:
        if own in known:
            return {"role": own, "how": "item", "detail": "the item names it"}
        return {"role": None, "how": "needs_label", "detail": f"unknown role {own}"}
    table = work_types()
    kind = (item.get("kind") or "").strip().lower()
    if kind in table["kinds"] and table["kinds"][kind] in known:
        return {"role": table["kinds"][kind], "how": "kind", "detail": f"kind {kind}"}
    if kind in table["person_work"]:
        return {"role": None, "how": "person", "detail": f"kind {kind} is person work"}
    return {"role": "planner", "how": "needs_label", "detail": f"kind {kind or 'none'} does not say what the hand-back is: the planner proposes a role"}


def role_for(item: dict) -> dict:
    """The card for a work item: its `role`, else the default (builder). Unknown role -> KeyError."""
    return roles()[item.get("role") or DEFAULT]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["list"]:
        for rid, row in roles().items():
            print(f"{rid} ({row['source']}): {row['does']}")
        return 0
    if argv[:1] == ["card"] and len(argv) == 2:
        card = roles().get(argv[1])
        if card is None:
            print(json.dumps({"error": f"no role {argv[1]}"}))
            return 1
        print(json.dumps(card, indent=1))
        return 0
    if argv[:1] == ["resolve"] and len(argv) == 2:
        print(json.dumps(resolve(json.loads(argv[1])), indent=1))
        return 0
    if argv[:1] == ["check"]:
        found = local_problems()
        print(json.dumps({"ok": not found, "problems": found}, indent=1))
        return 1 if found else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
