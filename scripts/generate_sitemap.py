#!/usr/bin/env python3

from pathlib import Path
from html.parser import HTMLParser
import html
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".github",
    "includes",
    "includes_es",
    "node_modules",
    "_site",
    "vendor",
}

SKIP_FILES = {
    "404.html",
}


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.alternates = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return

        attrs = dict(attrs)
        rel = (attrs.get("rel") or "").lower()
        href = attrs.get("href")
        hreflang = attrs.get("hreflang")

        if rel == "canonical" and href:
            self.canonical = href

        if rel == "alternate" and href and hreflang:
            self.alternates[hreflang] = href


def discover_pages():
    pages = []

    for path in ROOT.rglob("*.html"):
        rel = path.relative_to(ROOT)

        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        if path.name in SKIP_FILES:
            continue

        text = path.read_text(encoding="utf-8")

        if re.search(
            r'<meta\b(?=[^>]*name=["\']robots["\'])'
            r'(?=[^>]*content=["\'][^"\']*noindex)',
            text,
            re.I,
        ):
            continue

        parser = MetaParser()
        parser.feed(text)

        if not parser.canonical:
            print(f"ERROR: no canonical: {rel}", file=sys.stderr)
            raise SystemExit(1)

        pages.append((rel, parser.canonical, parser.alternates))

    return sorted(pages, key=lambda x: x[1])


def esc(value):
    return html.escape(value, quote=True)


def main():
    pages = discover_pages()
    seen = set()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset',
        '  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '  xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]

    for rel, canonical, alternates in pages:
        if canonical in seen:
            print(f"ERROR: duplicate canonical: {canonical}", file=sys.stderr)
            return 1

        seen.add(canonical)

        lines.append("  <url>")
        lines.append(f"    <loc>{esc(canonical)}</loc>")

        for lang in ("en", "es", "x-default"):
            href = alternates.get(lang)
            if href:
                lines.append(
                    f'    <xhtml:link rel="alternate" '
                    f'hreflang="{lang}" href="{esc(href)}" />'
                )

        lines.append("  </url>")

    lines.append("</urlset>")

    output = ROOT / "sitemap.xml"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {output}")
    print(f"URLs: {len(pages)}")


if __name__ == "__main__":
    raise SystemExit(main())
