#!/usr/bin/env python3
"""Write one machine-readable reason: python3 platform/kit/reason.py CODE "detail" [--warn]

Prints a JSON line {"code","result","detail","next_action",...}, appends a line to $GITHUB_STEP_SUMMARY when set, and prints a GitHub
annotation (::error / ::warning) so the reason shows on the check. Unknown codes are refused. Never put a secret in the detail: it is
echoed to logs. Exit status: 0 for a warning or success results, 1 otherwise.
"""
import json
import os
import sys
from pathlib import Path

CATALOG = Path(__file__).with_name("reason_codes.json")


def lookup(code: str) -> dict | None:
    for row in json.loads(CATALOG.read_text())["codes"]:
        if row["code"] == code:
            return row
    return None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    warn = "--warn" in argv
    args = [a for a in argv if a != "--warn"]
    if len(args) != 2:
        print(__doc__)
        return 2
    code, detail = args
    row = lookup(code)
    if row is None:
        print(json.dumps({"code": "UNKNOWN", "detail": f"unknown reason code {code}"}))
        return 2
    detail = detail.replace("\n", " ")[:500]
    record = {"code": code, "result": row["result"], "detail": detail, "next_action": row["next_action"], "owner_needed": row["owner_needed"], "retry": row["retry"]}
    print(json.dumps(record, sort_keys=True))
    print(f"::{'warning' if warn else 'error'} title={code}::{detail} -> {row['next_action']}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"**{row['result']} {code}**: {detail} -> {row['next_action']}\n")
    return 0 if warn else 1


if __name__ == "__main__":
    sys.exit(main())
