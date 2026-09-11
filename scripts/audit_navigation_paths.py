#!/usr/bin/env python3
"""Deterministically measure click distance through the static site's internal link graph."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import deque
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "tnk-site-navigation-paths-v1"
ROOT = Path(__file__).resolve().parent.parent


def load_integrity_module():
    """Load the existing site parser/link resolver so this tool shares release semantics."""
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import check_site_integrity as integrity  # type: ignore

    return integrity


def build_graph(root: Path, integrity: Any) -> dict[str, set[str]]:
    """Return page -> directly linked standalone pages using the integrity contract."""
    root = root.resolve()
    pages = list(integrity.discover_pages(root))
    page_set = set(pages)
    graph: dict[str, set[str]] = {rel.as_posix(): set() for rel in pages}

    for rel in pages:
        parser = integrity.parse_page(root / rel)
        source = rel.as_posix()
        for href in parser.links:
            target, _fragment = integrity.resolve_internal_target(root, rel, href)
            if target is None or not target.is_file():
                continue
            try:
                target_rel = target.relative_to(root)
            except ValueError:
                continue
            if target_rel not in page_set or target_rel == rel:
                continue
            graph[source].add(target_rel.as_posix())
    return graph


def shortest_paths(graph: dict[str, set[str]], start: str) -> tuple[dict[str, int], dict[str, str | None]]:
    if start not in graph:
        raise ValueError(f"entry page is not a discovered standalone page: {start}")
    distances = {start: 0}
    previous: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for target in sorted(graph[current]):
            if target in distances:
                continue
            distances[target] = distances[current] + 1
            previous[target] = current
            queue.append(target)
    return distances, previous


def reconstruct_path(previous: dict[str, str | None], page: str) -> list[str]:
    if page not in previous:
        return []
    path = []
    cursor: str | None = page
    while cursor is not None:
        path.append(cursor)
        cursor = previous[cursor]
    return list(reversed(path))


def entry_report(graph: dict[str, set[str]], start: str) -> dict[str, Any]:
    distances, previous = shortest_paths(graph, start)
    pages = sorted(graph)
    unreachable = [page for page in pages if page not in distances]
    reachable_distances = [distance for page, distance in distances.items() if page != start]
    histogram: dict[str, int] = {}
    for distance in reachable_distances:
        key = str(distance)
        histogram[key] = histogram.get(key, 0) + 1
    longest_distance = max(reachable_distances, default=0)
    longest_pages = sorted(page for page, distance in distances.items() if distance == longest_distance and page != start)
    rows = []
    for page in sorted(distances, key=lambda item: (distances[item], item)):
        rows.append({
            "page": page,
            "clicks": distances[page],
            "path": reconstruct_path(previous, page),
        })
    return {
        "entry_page": start,
        "reachable_page_count": len(distances),
        "unreachable_page_count": len(unreachable),
        "unreachable_pages": unreachable,
        "mean_clicks": round(statistics.fmean(reachable_distances), 3) if reachable_distances else 0.0,
        "median_clicks": statistics.median(reachable_distances) if reachable_distances else 0.0,
        "max_clicks": longest_distance,
        "longest_pages": longest_pages,
        "click_histogram": dict(sorted(histogram.items(), key=lambda item: int(item[0]))),
        "pages": rows,
    }


def build_report(graph: dict[str, set[str]], starts: list[str]) -> dict[str, Any]:
    incoming = {page: 0 for page in graph}
    edge_count = 0
    for targets in graph.values():
        edge_count += len(targets)
        for target in targets:
            if target in incoming:
                incoming[target] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "deterministic": True,
        "network_access": False,
        "page_count": len(graph),
        "internal_page_edge_count": edge_count,
        "zero_incoming_pages": sorted(page for page, count in incoming.items() if count == 0),
        "zero_outgoing_pages": sorted(page for page, targets in graph.items() if not targets),
        "entries": [entry_report(graph, start) for start in starts],
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"Navigation path audit: {report['page_count']} pages, {report['internal_page_edge_count']} internal page links."
    ]
    for entry in report["entries"]:
        lines.append(
            f"Entry {entry['entry_page']}: {entry['reachable_page_count']}/{report['page_count']} reachable; "
            f"median {entry['median_clicks']} clicks; mean {entry['mean_clicks']}; max {entry['max_clicks']}; "
            f"unreachable {entry['unreachable_page_count']}."
        )
        if entry["longest_pages"]:
            lines.append("  Longest: " + ", ".join(entry["longest_pages"]))
        if entry["unreachable_pages"]:
            lines.append("  Unreachable: " + ", ".join(entry["unreachable_pages"]))
    if report["zero_incoming_pages"]:
        lines.append("Zero incoming links: " + ", ".join(report["zero_incoming_pages"]))
    if report["zero_outgoing_pages"]:
        lines.append("Zero outgoing links: " + ", ".join(report["zero_outgoing_pages"]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="site repository root")
    parser.add_argument("--start", action="append", dest="starts", help="entry page relative to root; repeatable")
    parser.add_argument("--json-output", type=Path, help="write the complete deterministic report as JSON")
    parser.add_argument("--json", action="store_true", help="print JSON instead of the compact text summary")
    args = parser.parse_args()

    starts = args.starts or ["index.html"]
    try:
        graph = build_graph(args.root, load_integrity_module())
        report = build_report(graph, starts)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered_json = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered_json, encoding="utf-8")
    print(rendered_json if args.json else render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
