#!/usr/bin/env python3
"""Summarize privacy-bounded GA4 page/referrer aggregates into page transitions.

This tool intentionally consumes aggregate rows only. It does not query GA4, persist
visitor identifiers, or infer person-level journeys.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


SCHEMA_VERSION = "tnk-ga4-page-transitions-v1"
DEFAULT_SITE_ORIGIN = "https://titoneedsakidney.com"
REQUIRED_COLUMNS = ("hostName", "pageReferrer", "pagePath", "screenPageViews")
FORBIDDEN_DIMENSIONS = {
    "client_id",
    "clientid",
    "email",
    "ga_session_id",
    "gasessionid",
    "session_id",
    "sessionid",
    "user_id",
    "userid",
    "userprovideddata",
    "user_pseudo_id",
    "userpseudoid",
    "userpseudonymousid",
}
MISSING_VALUES = {"", "(not set)", "(direct)", "(none)"}


class InputError(ValueError):
    """Raised when an input export violates the aggregate-report contract."""


@dataclass(frozen=True)
class TransitionRow:
    host: str
    page_referrer: str
    page_path: str
    views: int


def _canonical_header(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch == "_")


def validate_headers(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise InputError("input CSV has no header row")

    canonical = {_canonical_header(name): name for name in fieldnames}
    forbidden = sorted(name for name in canonical if name in FORBIDDEN_DIMENSIONS)
    if forbidden:
        original = ", ".join(canonical[name] for name in forbidden)
        raise InputError(
            "visitor/session-level identifier columns are not allowed: " + original
        )

    missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
    if missing:
        raise InputError("missing required columns: " + ", ".join(missing))


def parse_views(value: str, line_number: int) -> int:
    raw = value.strip().replace(",", "")
    if not raw:
        raise InputError(f"line {line_number}: screenPageViews is empty")
    try:
        number = float(raw)
    except ValueError as exc:
        raise InputError(
            f"line {line_number}: invalid screenPageViews value {value!r}"
        ) from exc
    if number < 0 or not number.is_integer():
        raise InputError(
            f"line {line_number}: screenPageViews must be a non-negative integer"
        )
    return int(number)


def canonicalize_path(value: str) -> str:
    raw = value.strip()
    if not raw or raw in MISSING_VALUES:
        raise InputError("pagePath is missing")

    parsed = urlsplit(raw)
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = "/" + path

    # Match the repository's canonical URL convention: directory indexes use a
    # trailing slash; leaf pages retain their explicit .html path.
    if path == "/index.html":
        return "/"
    if path.endswith("/index.html"):
        return path[: -len("index.html")]
    return path


def normalize_referrer(value: str, canonical_host: str) -> str | None:
    raw = value.strip()
    if raw.lower() in MISSING_VALUES:
        return None

    if raw.startswith("/"):
        return canonicalize_path(raw)

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.hostname is None or parsed.hostname.lower() != canonical_host:
        return None
    return canonicalize_path(parsed.path or "/")


def load_rows(path: Path) -> list[TransitionRow]:
    rows: list[TransitionRow] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        validate_headers(reader.fieldnames)
        for line_number, row in enumerate(reader, start=2):
            rows.append(
                TransitionRow(
                    host=(row.get("hostName") or "").strip().lower(),
                    page_referrer=(row.get("pageReferrer") or "").strip(),
                    page_path=(row.get("pagePath") or "").strip(),
                    views=parse_views(row.get("screenPageViews") or "", line_number),
                )
            )
    return rows


def build_report(
    rows: list[TransitionRow],
    site_origin: str = DEFAULT_SITE_ORIGIN,
    min_page_views: int = 3,
    min_transition_views: int = 3,
    top: int = 20,
) -> dict:
    parsed_origin = urlsplit(site_origin)
    if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.hostname:
        raise InputError(f"invalid site origin: {site_origin!r}")
    canonical_host = parsed_origin.hostname.lower()
    if min_page_views < 1:
        raise InputError("min_page_views must be at least 1")
    if min_transition_views < 1:
        raise InputError("min_transition_views must be at least 1")
    if top < 1:
        raise InputError("top must be at least 1")

    page_views: Counter[str] = Counter()
    entry_views: Counter[str] = Counter()
    outgoing_views: Counter[str] = Counter()
    incoming_views: Counter[str] = Counter()
    reload_views: Counter[str] = Counter()
    transitions: Counter[tuple[str, str]] = Counter()
    ignored_host_views = 0
    production_rows = 0

    for row in rows:
        if row.host != canonical_host:
            ignored_host_views += row.views
            continue
        production_rows += 1
        page = canonicalize_path(row.page_path)
        page_views[page] += row.views
        referrer = normalize_referrer(row.page_referrer, canonical_host)
        if referrer is None:
            entry_views[page] += row.views
        elif referrer == page:
            reload_views[page] += row.views
        else:
            transitions[(referrer, page)] += row.views
            outgoing_views[referrer] += row.views
            incoming_views[page] += row.views

    pages = []
    for page in sorted(page_views):
        views = page_views[page]
        if views < min_page_views:
            continue
        pages.append(
            {
                "page": page,
                "page_views": views,
                "entry_or_external_referrer_views": entry_views[page],
                "observed_incoming_same_site_transition_views": incoming_views[page],
                "observed_outgoing_same_site_transition_views": outgoing_views[page],
                "same_page_referrer_views": reload_views[page],
                "no_observed_same_site_next_page": outgoing_views[page] == 0,
            }
        )

    eligible_transitions = [
        (key, views) for key, views in transitions.items() if views >= min_transition_views
    ]
    ranked_transitions = [
        {"from": source, "to": destination, "views": views}
        for (source, destination), views in sorted(
            eligible_transitions,
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )[:top]
    ]

    no_next = [
        item["page"]
        for item in sorted(pages, key=lambda item: (-item["page_views"], item["page"]))
        if item["no_observed_same_site_next_page"]
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "site_origin": site_origin.rstrip("/"),
        "input_rows": len(rows),
        "production_rows": production_rows,
        "ignored_nonproduction_views": ignored_host_views,
        "min_page_views": min_page_views,
        "min_transition_views": min_transition_views,
        "suppressed_low_count_transition_pairs": sum(
            1 for views in transitions.values() if views < min_transition_views
        ),
        "production_page_views": sum(page_views.values()),
        "entry_or_external_referrer_views": sum(entry_views.values()),
        "same_site_transition_views": sum(transitions.values()),
        "same_page_referrer_views": sum(reload_views.values()),
        "top_transitions": ranked_transitions,
        "pages_without_observed_same_site_next_page": no_next,
        "pages": pages,
        "interpretation_boundary": (
            "Aggregate pageReferrer/pagePath counts are directional evidence only; "
            "they are not user-level journeys, exact exits, funnels, or proof of causality."
        ),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# GA4 aggregate page-transition report",
        "",
        f"- Production page views represented: **{report['production_page_views']}**",
        f"- Same-site transition views observed: **{report['same_site_transition_views']}**",
        f"- Entry/external-referrer views: **{report['entry_or_external_referrer_views']}**",
        f"- Same-page referrer/reload views: **{report['same_page_referrer_views']}**",
        f"- Non-production-host views ignored: **{report['ignored_nonproduction_views']}**",
        "",
        "> " + report["interpretation_boundary"],
        "",
        "## Top observed same-site transitions",
        "",
        "| From | To | Views |",
        "|---|---|---:|",
    ]
    if report["top_transitions"]:
        lines.extend(
            f"| `{item['from']}` | `{item['to']}` | {item['views']} |"
            for item in report["top_transitions"]
        )
    else:
        lines.append("| _None observed_ |  | 0 |")

    lines.extend(
        [
            "",
            "## Pages with no observed same-site next page",
            "",
            "This is a review queue, **not an exit-rate calculation**. A page can appear here "
            "because the visit ended, moved off-site, lost referrer information, or had too little traffic.",
            "",
        ]
    )
    if report["pages_without_observed_same_site_next_page"]:
        lines.extend(
            f"- `{page}`" for page in report["pages_without_observed_same_site_next_page"]
        )
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_output(path: Path | None, content: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="aggregate GA4 CSV export")
    parser.add_argument("--site-origin", default=DEFAULT_SITE_ORIGIN)
    parser.add_argument("--min-page-views", type=int, default=3)
    parser.add_argument("--min-transition-views", type=int, default=3)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = load_rows(args.input)
        report = build_report(
            rows,
            site_origin=args.site_origin,
            min_page_views=args.min_page_views,
            min_transition_views=args.min_transition_views,
            top=args.top,
        )
    except (OSError, InputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)
    write_output(args.json_output, json_text)
    write_output(args.markdown_output, markdown_text)
    if args.json_output is None and args.markdown_output is None:
        print(json_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
