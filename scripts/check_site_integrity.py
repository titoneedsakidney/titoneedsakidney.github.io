#!/usr/bin/env python3
"""Lightweight release validation for the deployable bilingual HTML site."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

import update_static_metadata as metadata


ROOT = Path(__file__).resolve().parent.parent
DATA_INCLUDE_RE = re.compile(r"\bdata-include\s*=", re.I)
ROLE_TERMS = {
    "social worker": "social worker",
    "trabajador/a social": "social worker",
    "trabajador social": "social worker",
    "nephrologist": "nephrologist",
    "nefrólogo": "nephrologist",
    "nefrologo": "nephrologist",
}
REQUIRED_SCHEMAS = {
    Path("index.html"): "WebSite",
    Path("es/index.html"): "WebSite",
    Path("book.html"): "Book",
    Path("es/book.html"): "Book",
    Path("about.html"): "Person",
    Path("es/about.html"): "Person",
}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.ids = []
        self.h1_count = 0
        self.main_count = 0
        self.skip_targets = []
        self.canonicals = []
        self.alternates = []
        self.links = []
        self.title_parts = []
        self.h1_parts = []
        self.og_title = ""
        self.json_ld = []
        self._in_title = False
        self._in_h1 = False
        self._main_depth = 0
        self._suppressed_depth = 0
        self._head_depth = 0
        self._json_parts = None
        self._json_in_head = False
        self.visible_main_parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "head":
            self._head_depth += 1
        if tag == "main":
            self.main_count += 1
            self._main_depth += 1
        if tag == "h1":
            self.h1_count += 1
            self._in_h1 = True
        if tag in {"script", "style", "template"}:
            self._suppressed_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
            if "skip-link" in attrs.get("class", "").split():
                self.skip_targets.append(attrs["href"])
        if tag == "link":
            rel = attrs.get("rel", "").lower().split()
            if "canonical" in rel and attrs.get("href"):
                self.canonicals.append(attrs["href"])
            if "alternate" in rel and attrs.get("href") and attrs.get("hreflang"):
                self.alternates.append((attrs["hreflang"].lower(), attrs["href"]))
        if tag == "meta" and attrs.get("property", "").lower() == "og:title":
            self.og_title = attrs.get("content", "")
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._json_parts = []
            self._json_in_head = bool(self._head_depth)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag == "script" and self._json_parts is not None:
            self.json_ld.append(("".join(self._json_parts), self._json_in_head))
            self._json_parts = None
        if tag in {"script", "style", "template"} and self._suppressed_depth:
            self._suppressed_depth -= 1
        if tag == "main" and self._main_depth:
            self._main_depth -= 1
        if tag == "head" and self._head_depth:
            self._head_depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)
        if self._json_parts is not None:
            self._json_parts.append(data)
        if self._main_depth and not self._suppressed_depth:
            self.visible_main_parts.append(data)

    @property
    def title(self):
        return normalize_text(" ".join(self.title_parts))

    @property
    def visible_body(self):
        return normalize_text(" ".join(self.visible_main_parts))

    @property
    def h1(self):
        return normalize_text(" ".join(self.h1_parts))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def discover_pages(root: Path) -> list[Path]:
    pages = []
    for path in root.rglob("*.html"):
        rel = path.relative_to(root)
        if any(part in metadata.SKIP_DIRS for part in rel.parts):
            continue
        if path.name in metadata.SKIP_FILES:
            continue
        if re.search(r"<meta\b(?=[^>]*name=[\"']robots[\"'])"
                     r"(?=[^>]*content=[\"'][^\"']*noindex)",
                     path.read_text(encoding="utf-8"), re.I):
            continue
        pages.append(rel)
    return sorted(pages)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def role_in(value: str) -> set[str]:
    lowered = value.lower()
    return {role for term, role in ROLE_TERMS.items() if term in lowered}


def expected_alternates(rel: Path, pages: set[Path]) -> dict[str, str]:
    lang = "es" if rel.parts and rel.parts[0] == "es" else "en"
    counterpart = metadata.counterpart_for(rel, pages)
    en_url, es_url = metadata.language_urls(rel, lang, counterpart)
    expected = {}
    if en_url:
        expected["en"] = en_url
        expected["x-default"] = en_url
    if es_url:
        expected["es"] = es_url
    return expected


def check_json_ld(rel: Path, parser: PageParser) -> list[str]:
    errors = []
    types = set()
    canonical = metadata.absolute_url(rel)
    for raw, in_head in parser.json_ld:
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON-LD: {exc.msg}")
            continue
        if not in_head:
            errors.append("JSON-LD must be placed in <head>")
        entries = item if isinstance(item, list) else [item]
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append("JSON-LD item is not an object")
                continue
            schema_type = entry.get("@type")
            if schema_type:
                types.add(schema_type)
                if schema_type in {"Book", "Person", "WebSite"} and entry.get("url") != canonical:
                    errors.append(f"{schema_type} JSON-LD URL does not match canonical")
    required = REQUIRED_SCHEMAS.get(rel)
    if required and required not in types:
        errors.append(f"missing required {required} JSON-LD")
    return errors


def check_page(root: Path, rel: Path, pages: set[Path]) -> list[str]:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    parser = parse_page(path)
    errors = []
    expected_lang = "es" if rel.parts and rel.parts[0] == "es" else "en"

    if parser.lang != expected_lang:
        errors.append(f"lang is {parser.lang!r}, expected {expected_lang!r}")
    duplicate_ids = sorted(identifier for identifier, count in Counter(parser.ids).items() if count > 1)
    if duplicate_ids:
        errors.append("duplicate id values: " + ", ".join(duplicate_ids))
    if parser.h1_count != 1:
        errors.append(f"expected exactly one H1, found {parser.h1_count}")
    if parser.main_count != 1:
        errors.append(f"expected exactly one main landmark, found {parser.main_count}")
    if not parser.skip_targets:
        errors.append("missing skip link")
    for target in parser.skip_targets:
        if not target.startswith("#") or target[1:] not in parser.ids:
            errors.append(f"skip-link target does not exist: {target}")
    expected_canonical = metadata.absolute_url(rel)
    if parser.canonicals != [expected_canonical]:
        errors.append(f"canonical is {parser.canonicals}, expected [{expected_canonical}]")
    actual_alternates = dict(parser.alternates)
    expected = expected_alternates(rel, pages)
    if actual_alternates != expected or len(parser.alternates) != len(actual_alternates):
        errors.append("hreflang alternates do not match the bilingual counterpart")
    if DATA_INCLUDE_RE.search(text):
        errors.append("runtime data-include placeholder remains")
    title_roles = role_in(parser.title) | role_in(parser.og_title)
    h1_roles = role_in(parser.h1)
    if title_roles and h1_roles and title_roles.isdisjoint(h1_roles):
        errors.append("role named by title/metadata conflicts with H1 content")
    errors.extend(check_json_ld(rel, parser))
    return errors


def resolve_internal_target(root: Path, rel: Path, href: str) -> tuple[Path | None, str | None]:
    parsed = urlsplit(href)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None, None
    if parsed.netloc and parsed.netloc != urlsplit(metadata.SITE_URL).netloc:
        return None, None
    raw_path = unquote(parsed.path)
    if not raw_path:
        candidate = root / rel
    else:
        candidate = root / raw_path.lstrip("/") if raw_path.startswith("/") else (root / rel.parent / raw_path)
    try:
        candidate = candidate.resolve()
        candidate.relative_to(root.resolve())
    except ValueError:
        return Path("/outside-site"), parsed.fragment or None
    if candidate.is_dir() or raw_path.endswith("/"):
        candidate /= "index.html"
    return candidate, parsed.fragment or None


def check_links(root: Path, pages: list[Path]) -> list[tuple[Path, str]]:
    errors = []
    parsed_pages = {rel: parse_page(root / rel) for rel in pages}
    for rel, parser in parsed_pages.items():
        for href in parser.links:
            target, fragment = resolve_internal_target(root, rel, href)
            if target is None:
                continue
            if not target.is_file():
                errors.append((rel, f"broken internal link: {href}"))
                continue
            if fragment:
                target_rel = target.relative_to(root)
                target_parser = parsed_pages.get(target_rel) or parse_page(target)
                if fragment not in target_parser.ids:
                    errors.append((rel, f"missing fragment target in {href}"))
    return errors


def load_duplicate_allowlist(root: Path) -> set[frozenset[str]]:
    path = root / "scripts" / "integrity_allowlist.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {frozenset(item) for item in data.get("duplicate_visible_bodies", []) if len(item) == 2}
    except (json.JSONDecodeError, TypeError):
        return set()


def check_duplicate_bodies(root: Path, pages: list[Path]) -> list[tuple[Path, str]]:
    allowlist = load_duplicate_allowlist(root)
    seen = {}
    errors = []
    for rel in pages:
        body = parse_page(root / rel).visible_body
        if not body:
            continue
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if digest in seen:
            pair = frozenset({seen[digest].as_posix(), rel.as_posix()})
            if pair not in allowlist:
                errors.append((rel, f"duplicate visible main body: {seen[digest]}"))
        else:
            seen[digest] = rel
    return errors


def check_sitemap(root: Path, pages: list[Path]) -> list[str]:
    sitemap = root / "sitemap.xml"
    if not sitemap.exists():
        return ["sitemap.xml is missing"]
    try:
        tree = ElementTree.parse(sitemap)
    except ElementTree.ParseError as exc:
        return [f"invalid sitemap.xml: {exc}"]
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    actual = {node.text for node in tree.findall(f".//{namespace}loc") if node.text}
    expected = {metadata.absolute_url(rel) for rel in pages}
    if actual != expected:
        return ["sitemap membership does not match canonical standalone pages"]
    return []


def run_composed_checks(root: Path) -> int:
    commands = [
        ["scripts/expand_includes.py", "--check"],
        ["scripts/update_static_metadata.py", "--check"],
        ["scripts/update_structured_data.py", "--check"],
        ["scripts/generate_sitemap.py", "--check"],
    ]
    failures = 0
    for command in commands:
        result = subprocess.run([sys.executable, *command], cwd=root, check=False)
        failures += result.returncode != 0
    return failures


def audit(root: Path) -> int:
    pages = discover_pages(root)
    page_set = set(pages)
    failures = 0
    for rel in pages:
        errors = check_page(root, rel, page_set)
        if errors:
            failures += 1
            print(f"FAIL: {rel}")
            for error in errors:
                print(f"  - {error}")
    for rel, error in check_links(root, pages) + check_duplicate_bodies(root, pages):
        failures += 1
        print(f"FAIL: {rel}\n  - {error}")
    for error in check_sitemap(root, pages):
        failures += 1
        print(f"FAIL: sitemap.xml\n  - {error}")
    if failures:
        print(f"\n{failures} integrity failure(s).")
        return 1
    print(f"PASS: {len(pages)} standalone pages passed integrity checks.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-composed-checks", action="store_true")
    args = parser.parse_args()
    if not args.skip_composed_checks and run_composed_checks(ROOT):
        return 1
    return audit(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
