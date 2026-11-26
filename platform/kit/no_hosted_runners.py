#!/usr/bin/env python3
"""No-billing guard: fail if any GitHub Actions workflow would run on a GitHub-hosted (billed) runner.

Part of the platform kit (source: automationpc-platform kit/no_hosted_runners.py; the platform's own copy is tools/no_hosted_runners.py).
The table-rules workflow runs it in every repo: no repo may spend GitHub-hosted minutes (owner decision no-github-billing).

Standalone and copyable into any repo (standard library only). It reads each `.github/workflows/*.yml|yaml`
line by line, so it needs no YAML parser, and refuses anything it cannot prove is self-hosted:
  - `runs-on:` values starting with ubuntu-, windows-, macos- (including -latest and -arm) fail;
  - a `runs-on` that is not a literal self-hosted list (an expression, a matrix variable, a bare label) fails;
  - a job with no `runs-on` (reusable-workflow `uses:` jobs are exempt) fails.

  no_hosted_runners.py [REPO_ROOT]        prints JSON; exit 0 when clean, 1 otherwise
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HOSTED = re.compile(r"^(ubuntu|windows|macos)(-|$)", re.I)
RUNS_ON = re.compile(r"^(\s*)runs-on:\s*(.*?)\s*(#.*)?$")


def labels(value: str) -> list[str] | None:
    """Labels of a literal `runs-on` value, or None when it is not a plain literal (expression, block scalar)."""
    value = value.strip()
    if not value or value.startswith(("${{", "|", ">", "&", "*")):
        return None
    if value.startswith("["):
        if not value.endswith("]"):
            return None
        parts = [p.strip().strip("'\"") for p in value[1:-1].split(",")]
    else:
        parts = [value.strip("'\"")]
    if any(not p or "${{" in p for p in parts):
        return None
    return parts


def check_text(text: str, name: str = "workflow") -> list[dict]:
    problems: list[dict] = []
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        match = RUNS_ON.match(line)
        if not match:
            continue
        value = match.group(2)
        if value == "":  # block list form:  runs-on:\n  - self-hosted
            block = []
            for follow in lines[number:]:
                item = re.match(r"^\s*-\s*(.+?)\s*(#.*)?$", follow)
                if not item:
                    break
                block.append(item.group(1).strip("'\""))
            found = block or None
        else:
            found = labels(value)
        if found is None:
            problems.append({"file": name, "line": number, "problem": "runs-on is not a literal list of labels; cannot prove it is self-hosted"})
        elif any(HOSTED.match(label) for label in found):
            problems.append({"file": name, "line": number, "problem": f"GitHub-hosted runner {found} would be billed"})
        elif "self-hosted" not in [label.lower() for label in found]:
            problems.append({"file": name, "line": number, "problem": f"runs-on {found} does not include self-hosted"})
    # jobs without runs-on
    in_jobs = False
    job_indent = None
    current, has_runs, has_uses = None, False, False
    for number, line in enumerate(lines, start=1):
        if re.match(r"^jobs:\s*$", line):
            in_jobs, job_indent = True, None
            continue
        if in_jobs and re.match(r"^\S", line) and line.strip() and not line.startswith("#"):
            in_jobs = False
        if not in_jobs or not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if job_indent is None:
            job_indent = indent
        if indent == job_indent and re.match(r"^\s*[\w.-]+:\s*$", line):
            if current and not has_runs and not has_uses:
                problems.append({"file": name, "line": current[1], "problem": f"job {current[0]} has no runs-on"})
            current, has_runs, has_uses = (line.strip().rstrip(":"), number), False, False
        elif current and indent == job_indent + 2 and line.strip().startswith("runs-on:"):
            has_runs = True
        elif current and indent == job_indent + 2 and line.strip().startswith("uses:"):
            has_uses = True
    if current and not has_runs and not has_uses:
        problems.append({"file": name, "line": current[1], "problem": f"job {current[0]} has no runs-on"})
    return problems


def check_repo(root: Path) -> dict:
    files = sorted([*(root / ".github" / "workflows").glob("*.yml"), *(root / ".github" / "workflows").glob("*.yaml")])
    problems = []
    for path in files:
        problems.extend(check_text(path.read_text(encoding="utf-8"), path.name))
    return {"contract": "no-hosted-runners-v1", "workflows": len(files), "ok": not problems, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    root = Path((argv or sys.argv[1:] or ["."])[0]).resolve()
    result = check_repo(root)
    print(json.dumps(result, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
