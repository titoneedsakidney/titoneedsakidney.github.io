#!/usr/bin/env python3
"""Build the minimal static artifact published by the GitHub Pages workflow."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import argparse
import shutil

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git",
    ".github",
    "_site",
    "docs",
    "includes",
    "includes_es",
    "node_modules",
    "scripts",
    "tests",
    "vendor",
}
STATIC_DIRS = ("assets", "data")
ROOT_FILES = ("CNAME", "robots.txt", "sitemap.xml")


class RobotsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.noindex = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "meta":
            return
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        if values.get("name", "").lower() == "robots" and "noindex" in values.get("content", "").lower():
            self.noindex = True


def is_deployable_html(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    parser = RobotsParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return not parser.noindex


def build(output: Path) -> dict[str, int]:
    output = output.resolve()
    if output == ROOT.resolve() or ROOT.resolve() in output.parents and output.name != "_site":
        raise ValueError("output must be a dedicated artifact directory")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    pages = 0
    for source in ROOT.rglob("*.html"):
        if not is_deployable_html(source):
            continue
        rel = source.relative_to(ROOT)
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        pages += 1

    static_files = 0
    for name in STATIC_DIRS:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, output / name, dirs_exist_ok=True)
            static_files += sum(1 for p in source.rglob("*") if p.is_file())

    root_files = 0
    for name in ROOT_FILES:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, output / name)
            root_files += 1

    if not (output / "index.html").is_file():
        raise ValueError("artifact is missing index.html")
    if not (output / "CNAME").is_file():
        raise ValueError("artifact is missing CNAME")
    return {"pages": pages, "static_files": static_files, "root_files": root_files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()
    result = build(ROOT / args.output)
    print(f"PAGES_ARTIFACT_READY pages={result['pages']} static_files={result['static_files']} root_files={result['root_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
