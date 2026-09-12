#!/usr/bin/env python3
"""Reduce aggregate Search Console exports into privacy-safe review candidates.

The reducer is deliberately read-only and offline.  It accepts aggregate
page/query rows, validates their shape, aggregates duplicates, and identifies
high-impression / low-click review candidates.  Query text is redacted by
default; callers must explicitly opt in to include it in private local output.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Iterable


SCHEMA_VERSION = "tnk-search-console-opportunity-v1"
SENSITIVE_HEADERS = {
    "clientid",
    "client_id",
    "userid",
    "user_id",
    "sessionid",
    "session_id",
    "visitorid",
    "visitor_id",
    "ga_session_id",
    "fullvisitorid",
}
ALIASES = {
    "query": {"query", "queries", "topquery", "topqueries"},
    "page": {"page", "pages", "toppage", "toppages"},
    "clicks": {"click", "clicks"},
    "impressions": {"impression", "impressions"},
    "ctr": {"ctr", "clickthroughrate", "clickthrough"},
    "position": {"position", "averageposition", "avgposition"},
}


class SearchConsoleReportError(ValueError):
    """Input is unsafe, incomplete, or inconsistent."""


@dataclass(frozen=True)
class Row:
    query: str
    page: str | None
    clicks: int
    impressions: int
    position: float


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", value.casefold().strip())


def _field_map(headers: Iterable[str]) -> dict[str, str]:
    headers = tuple(headers)
    normalized = {_header_key(header): header for header in headers}
    sensitive = sorted(name for name in normalized if name in SENSITIVE_HEADERS)
    if sensitive:
        raise SearchConsoleReportError(
            "visitor/session identifier columns are not accepted: " + ", ".join(sensitive)
        )
    mapped: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapped[canonical] = normalized[alias]
                break
    required = {"query", "clicks", "impressions", "position"}
    missing = sorted(required - mapped.keys())
    if missing:
        raise SearchConsoleReportError(
            "missing required Search Console columns: " + ", ".join(missing)
        )
    return mapped


def _parse_int(value: str, *, field: str) -> int:
    text = value.strip().replace(",", "")
    try:
        parsed = int(text)
    except ValueError as exc:
        raise SearchConsoleReportError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise SearchConsoleReportError(f"{field} must not be negative")
    return parsed


def _parse_position(value: str) -> float:
    try:
        parsed = float(value.strip())
    except ValueError as exc:
        raise SearchConsoleReportError("position must be numeric") from exc
    if parsed <= 0:
        raise SearchConsoleReportError("position must be greater than zero")
    return parsed


def _parse_ctr(value: str) -> float:
    text = value.strip()
    if not text:
        raise SearchConsoleReportError("CTR must not be blank")
    if text.endswith("%"):
        text = text[:-1].strip()
        divisor = 100.0
    else:
        divisor = 1.0
    try:
        parsed = float(text) / divisor
    except ValueError as exc:
        raise SearchConsoleReportError("CTR must be numeric or a percent") from exc
    if not 0 <= parsed <= 1:
        raise SearchConsoleReportError("CTR must be between 0 and 100%")
    return parsed


def _normalize_page(value: str) -> str:
    page = value.strip()
    if not page:
        return "/"
    # Search Console often exports full URLs.  Only retain the path-ish suffix
    # in the report so host/query fragments do not accidentally become public
    # evidence.
    match = re.match(r"^https?://[^/]+(?P<path>/.*)?$", page, flags=re.IGNORECASE)
    if match:
        page = match.group("path") or "/"
    page = page.split("#", 1)[0].split("?", 1)[0] or "/"
    if not page.startswith("/"):
        page = "/" + page
    return page


def read_rows(path: Path) -> tuple[list[Row], bool]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise SearchConsoleReportError("input file is unavailable") from exc
    with handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SearchConsoleReportError("input CSV has no header")
        fields = _field_map(reader.fieldnames)
        rows: list[Row] = []
        has_page = "page" in fields
        for line_number, raw in enumerate(reader, start=2):
            query = (raw.get(fields["query"]) or "").strip()
            if not query:
                raise SearchConsoleReportError(f"line {line_number}: query must not be blank")
            clicks = _parse_int(raw.get(fields["clicks"]) or "", field="clicks")
            impressions = _parse_int(
                raw.get(fields["impressions"]) or "", field="impressions"
            )
            if clicks > impressions:
                raise SearchConsoleReportError(
                    f"line {line_number}: clicks must not exceed impressions"
                )
            if "ctr" in fields:
                # Parse for shape validation, but counts remain canonical to
                # avoid Search Console display-rounding differences.
                _parse_ctr(raw.get(fields["ctr"]) or "")
            position = _parse_position(raw.get(fields["position"]) or "")
            page = None
            if has_page:
                page = _normalize_page(raw.get(fields["page"]) or "")
            rows.append(Row(query, page, clicks, impressions, position))
    if not rows:
        raise SearchConsoleReportError("input CSV contains no data rows")
    return rows, has_page


def _aggregate(rows: Iterable[Row]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str | None], dict[str, float | int]] = {}
    for row in rows:
        key = (row.query, row.page)
        item = grouped.setdefault(
            key, {"clicks": 0, "impressions": 0, "position_weight": 0.0}
        )
        item["clicks"] = int(item["clicks"]) + row.clicks
        item["impressions"] = int(item["impressions"]) + row.impressions
        item["position_weight"] = float(item["position_weight"]) + (
            row.position * row.impressions
        )
    result: list[dict[str, object]] = []
    for (query, page), item in grouped.items():
        impressions = int(item["impressions"])
        clicks = int(item["clicks"])
        if impressions <= 0:
            # A zero-impression row cannot support a ranking or weighted
            # position and is therefore not a useful Search Console signal.
            continue
        result.append(
            {
                "query": query,
                "page": page,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions, 6),
                "position": round(float(item["position_weight"]) / impressions, 3),
            }
        )
    return result


def build_report(
    rows: Iterable[Row],
    *,
    has_page: bool,
    min_impressions: int,
    max_ctr: float,
    max_position: float,
    include_query_text: bool,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, object]:
    if min_impressions < 1:
        raise SearchConsoleReportError("min_impressions must be at least 1")
    if not 0 <= max_ctr <= 1:
        raise SearchConsoleReportError("max_ctr must be between 0 and 1")
    if max_position <= 0:
        raise SearchConsoleReportError("max_position must be greater than zero")
    if (window_start is None) != (window_end is None):
        raise SearchConsoleReportError(
            "window_start and window_end must be supplied together"
        )
    if window_start is not None and window_end is not None:
        try:
            start = date.fromisoformat(window_start)
            end = date.fromisoformat(window_end)
        except ValueError as exc:
            raise SearchConsoleReportError(
                "observation window dates must use YYYY-MM-DD"
            ) from exc
        if start > end:
            raise SearchConsoleReportError("window_start must not be after window_end")

    aggregated = _aggregate(rows)
    candidates: list[dict[str, object]] = []
    for item in aggregated:
        if (
            int(item["impressions"]) < min_impressions
            or float(item["ctr"]) > max_ctr
            or float(item["position"]) > max_position
        ):
            continue
        candidates.append(
            {
                "query": item["query"],
                "page": item["page"] if has_page else None,
                "clicks": item["clicks"],
                "impressions": item["impressions"],
                "ctr": item["ctr"],
                "position": item["position"],
            }
        )

    candidates.sort(
        key=lambda item: (
            -int(item["impressions"]),
            float(item["ctr"]),
            float(item["position"]),
            str(item["query"]),
            str(item.get("page") or ""),
        )
    )

    page_summary: list[dict[str, object]] = []
    if has_page:
        by_page: dict[str, dict[str, int]] = {}
        candidate_keys = {
            (str(item["query"]), str(item["page"]))
            for item in candidates
        }
        for item in aggregated:
            page = str(item["page"])
            entry = by_page.setdefault(
                page, {"candidate_count": 0, "candidate_impressions": 0}
            )
            key = (str(item["query"]), page)
            if key in candidate_keys:
                entry["candidate_count"] += 1
                entry["candidate_impressions"] += int(item["impressions"])
        page_summary = [
            {"page": page, **counts}
            for page, counts in by_page.items()
            if counts["candidate_count"] > 0
        ]
        page_summary.sort(
            key=lambda item: (
                -int(item["candidate_impressions"]),
                -int(item["candidate_count"]),
                str(item["page"]),
            )
        )

    output_candidates: list[dict[str, object]] = []
    for index, item in enumerate(candidates, start=1):
        output_item = {
            "query_ref": f"q{index:04d}",
            "page": item["page"],
            "clicks": item["clicks"],
            "impressions": item["impressions"],
            "ctr": item["ctr"],
            "position": item["position"],
        }
        if include_query_text:
            output_item["query"] = item["query"]
        output_candidates.append(output_item)

    total_clicks = sum(int(item["clicks"]) for item in aggregated)
    total_impressions = sum(int(item["impressions"]) for item in aggregated)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "FACTS_READY",
        "query_text_included": include_query_text,
        "observation_window": (
            {"start": window_start, "end": window_end}
            if window_start is not None
            else None
        ),
        "filters": {
            "min_impressions": min_impressions,
            "max_ctr": max_ctr,
            "max_position": max_position,
            "meaning": (
                "review filter only; inclusion is not proof of a metadata/content defect"
            ),
        },
        "source_summary": {
            "aggregate_row_count": len(aggregated),
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "overall_ctr": round(total_clicks / total_impressions, 6)
            if total_impressions
            else 0.0,
            "has_page_dimension": has_page,
        },
        "candidate_count": len(output_candidates),
        "candidates": output_candidates,
        "page_summary": page_summary,
        "interpretation_boundary": (
            "Candidates identify aggregate Search Console rows worth private review. "
            "They do not establish user intent, causality, or a required site change."
        ),
    }


def render_markdown(report: dict[str, object]) -> str:
    filters = report["filters"]
    source = report["source_summary"]
    lines = [
        "# Search Console opportunity review",
        "",
        f"- Candidate rows: **{report['candidate_count']}**",
        f"- Aggregate rows: **{source['aggregate_row_count']}**",
        f"- Impressions: **{source['total_impressions']}**",
        f"- Clicks: **{source['total_clicks']}**",
        f"- Query text included: **{'yes' if report['query_text_included'] else 'no'}**",
        (
            "- Review filter: impressions >= "
            f"{filters['min_impressions']}, CTR <= {float(filters['max_ctr']) * 100:.1f}%, "
            f"position <= {filters['max_position']}"
        ),
        "",
        "> " + str(report["interpretation_boundary"]),
        "",
        "| Query | Page | Impressions | Clicks | CTR | Position |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in report["candidates"]:
        query = str(item.get("query") or item["query_ref"])
        page = str(item.get("page") or "—")
        lines.append(
            f"| `{query}` | `{page}` | {item['impressions']} | {item['clicks']} | "
            f"{float(item['ctr']) * 100:.2f}% | {float(item['position']):.2f} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce aggregate Search Console CSV rows into privacy-safe "
            "high-impression / low-click review candidates."
        )
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-impressions", type=int, default=25)
    parser.add_argument(
        "--max-ctr",
        type=float,
        default=0.05,
        help="decimal ratio, e.g. 0.05 for 5%%",
    )
    parser.add_argument("--max-position", type=float, default=10.0)
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument(
        "--include-query-text",
        action="store_true",
        help="include private raw query text in local output; redacted by default",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows, has_page = read_rows(args.input)
        report = build_report(
            rows,
            has_page=has_page,
            min_impressions=args.min_impressions,
            max_ctr=args.max_ctr,
            max_position=args.max_position,
            include_query_text=args.include_query_text,
            window_start=args.window_start,
            window_end=args.window_end,
        )
        rendered = (
            json.dumps(report, sort_keys=True, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(report)
        )
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except (SearchConsoleReportError, OSError) as exc:
        print(f"search-console-opportunity: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
