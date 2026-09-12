#!/usr/bin/env python3
"""Run the GA4 transition reducer directly on a native GA4 Exploration CSV.

Google Analytics Exploration exports include metadata comment lines, display-friendly
column names, and a Grand total row that do not match the reducer's canonical
four-column CSV contract. This adapter removes only that transport noise, preserves
the aggregate/privacy boundary, and reuses summarize_ga4_transitions for semantics.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import summarize_ga4_transitions as core


HEADER_ALIASES = {
    "host": {"hostname"},
    "referrer": {"pagereferrer"},
    "page": {
        "pagepath",
        "pagepathquerystring",
        "pagepathandscreenclass",
        "pagepathscreenclass",
        "pagepathquerystringandscreenclass",
    },
    "views": {"views", "screenpageviews"},
}


def _header_key(value: str) -> str:
    return "".join(ch for ch in value.casefold().strip() if ch.isalnum())


def _resolve_headers(fieldnames: list[str]) -> dict[str, int]:
    if not fieldnames:
        raise core.InputError("input CSV has no header row")

    normalized = [_header_key(name) for name in fieldnames]
    forbidden = {_header_key(name) for name in core.FORBIDDEN_DIMENSIONS}
    unsafe = [fieldnames[index] for index, key in enumerate(normalized) if key in forbidden]
    if unsafe:
        raise core.InputError(
            "visitor/session-level identifier columns are not allowed: "
            + ", ".join(unsafe)
        )

    resolved: dict[str, int] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        matches = [index for index, key in enumerate(normalized) if key in aliases]
        if len(matches) > 1:
            raise core.InputError(
                f"multiple columns match required GA4 field {canonical!r}"
            )
        if matches:
            resolved[canonical] = matches[0]

    missing = [name for name in HEADER_ALIASES if name not in resolved]
    if missing:
        raise core.InputError(
            "missing required GA4 columns: " + ", ".join(missing)
        )
    return resolved


def _is_google_grand_total(row: list[str], width: int, fields: dict[str, int]) -> bool:
    """Recognize the extra-cell Grand total row emitted by GA4 Exploration CSVs."""

    if len(row) != width + 1 or row[-1].strip().casefold() != "grand total":
        return False
    return all(
        not row[fields[name]].strip() for name in ("host", "referrer", "page")
    )


def load_native_rows(path: Path) -> list[core.TransitionRow]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise core.InputError("input CSV is unavailable") from exc

    with handle:
        data_lines = [
            line
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]

    if not data_lines:
        raise core.InputError("input CSV contains no tabular data")

    reader = csv.reader(data_lines)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise core.InputError("input CSV has no header row") from exc

    fields = _resolve_headers(header)
    rows: list[core.TransitionRow] = []
    for logical_line, row in enumerate(reader, start=2):
        if _is_google_grand_total(row, len(header), fields):
            continue
        if len(row) != len(header):
            raise core.InputError(
                f"line {logical_line}: unexpected column count {len(row)}; "
                f"expected {len(header)}"
            )

        rows.append(
            core.TransitionRow(
                host=row[fields["host"]].strip().lower(),
                page_referrer=row[fields["referrer"]].strip(),
                page_path=row[fields["page"]].strip(),
                views=core.parse_views(row[fields["views"]], logical_line),
            )
        )

    if not rows:
        raise core.InputError("input CSV contains no aggregate data rows")
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="native GA4 Exploration CSV export",
    )
    parser.add_argument("--site-origin", default=core.DEFAULT_SITE_ORIGIN)
    parser.add_argument("--min-page-views", type=int, default=3)
    parser.add_argument("--min-transition-views", type=int, default=3)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = load_native_rows(args.input)
        report = core.build_report(
            rows,
            site_origin=args.site_origin,
            min_page_views=args.min_page_views,
            min_transition_views=args.min_transition_views,
            top=args.top,
        )
    except (OSError, core.InputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown_text = core.render_markdown(report)
    core.write_output(args.json_output, json_text)
    core.write_output(args.markdown_output, markdown_text)
    if args.json_output is None and args.markdown_output is None:
        print(json_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
