#!/usr/bin/env python3
"""Executor unit lint in the repo's own CI (platform item ci-unit-lint-for-repos).

Part of the platform kit (source: automationpc-platform kit/unit_lint_check.py). A systemd unit the executor would refuse (a key not on its allow-list, a
protected path, User= root) used to fail only at release time and then block every release behind it. This runs the executor's own lint, the platform's copy of
executor/contract/validate.py delivered beside this file as validate.py (never a fork), on every unit this repo's platform/deploy-recipe.json installs through
host_files (a file whose target is `unit:<name>`), with the namespace's rules from unit_lint_rules.json (generated from the executor's host.json by the kit sync).

  unit_lint_check.py [REPO_ROOT]     prints JSON; exit 0 when every unit passes (or the repo installs none), 1 when one would be refused

Standard library only. A repo whose kit has no validate.py yet (an older kit) skips with a note, never a false failure."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_validate():
    path = HERE / "validate.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("platform_executor_validate", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("platform_executor_validate", module)
    spec.loader.exec_module(module)
    return module


def unit_files(recipe: dict, root: Path) -> list[tuple[str, str, Path]]:
    """(recipe unit id, unit file name, source path) for every `unit:` target of a host_files unit."""
    out = []
    for unit in recipe.get("units", []):
        if unit.get("kind") != "host_files":
            continue
        for f in unit.get("files", []):
            target = str(f.get("target", ""))
            if target.startswith("unit:") and f.get("source"):
                out.append((str(unit.get("id")), target[len("unit:"):], root / f["source"]))
    return out


def check(root: Path) -> dict:
    validate = load_validate()
    recipe_path, rules_path = root / "platform" / "deploy-recipe.json", HERE / "unit_lint_rules.json"
    if validate is None or not rules_path.is_file():
        return {"ok": True, "skipped": "this kit has no validate.py or unit_lint_rules.json yet", "problems": []}
    if not recipe_path.is_file():
        return {"ok": True, "skipped": "no platform/deploy-recipe.json: this repo installs no units", "problems": []}
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    ns = recipe.get("namespace")
    mine = (rules.get("namespaces") or {}).get(ns)
    if mine is None:
        return {"ok": False, "problems": [f"namespace {ns!r} is not in unit_lint_rules.json: run the kit sync"]}
    problems, checked = [], 0
    for unit_id, name, source in unit_files(recipe, root):
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            problems.append(f"{unit_id}: {name}: cannot read {source.relative_to(root)} as UTF-8 text")
            continue
        checked += 1
        found = validate.unit_lint(text, name, ns, service_users=mine.get("service_users", []), forbidden_users=rules.get("forbidden_users", []),
                                   protected_paths=rules.get("protected_paths", []), protected_groups=rules.get("protected_groups", []),
                                   root_units=mine.get("root_units", []))
        problems += [f"{unit_id}: {name}: {line}" for line in found]
    return {"ok": not problems, "namespace": ns, "units_checked": checked, "problems": problems}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    result = check(root)
    print(json.dumps(result, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
