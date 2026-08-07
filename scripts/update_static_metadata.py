#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


# ============================================================
# GLOBAL SITE METADATA
# Change these here, then rerun this script.
# ============================================================

SITE_URL = "https://titoneedsakidney.com"
THEME_COLOR = "#b24c63"

LANG_CONFIG = {
    "en": {
        "site_name": "Tito Needs a Kidney",
        "og_image": f"{SITE_URL}/assets/images/og-default.png",
        "og_image_alt": (
            "Cover of Tito Needs a Kidney: "
            "A Journey of Resilience, Community, and Hope"
        ),
    },
    "es": {
        "site_name": "Tito Necesita un Riñón",
        "og_image": f"{SITE_URL}/assets/images/og-spanish.png",
        "og_image_alt": (
            "Portada de Tito Necesita un Riñón: "
            "Un viaje de resiliencia, comunidad y esperanza"
        ),
    },
}

# Translation pairs whose filenames are intentionally different.
SPECIAL_PAIRS = {
    Path("for-professionals.html"): Path("es/para-profesionales.html"),
    Path("es/para-profesionales.html"): Path("for-professionals.html"),

    # Future pair, harmless until both files exist:
    Path("start-here.html"): Path("es/comienza-aqui.html"),
    Path("es/comienza-aqui.html"): Path("start-here.html"),
}

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

BEGIN = "<!-- STATIC SEO METADATA: BEGIN -->"
END = "<!-- STATIC SEO METADATA: END -->"


# ============================================================
# HTML READING
# ============================================================

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.lang = None
        self.title = ""
        self.description = None

        self.og_title = None
        self.og_description = None
        self.og_type = None

        self._in_title = False
        self._title_parts = []

        self._main_depth = 0
        self._collect_p = False
        self._p_parts = []
        self._p_class = ""
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()

        if tag == "html":
            self.lang = attrs.get("lang")

        elif tag == "title":
            self._in_title = True
            self._title_parts = []

        elif tag == "meta":
            name = (attrs.get("name") or "").lower()
            prop = (attrs.get("property") or "").lower()
            content = attrs.get("content")

            if name == "description" and content:
                self.description = content.strip()

            if prop == "og:title" and content:
                self.og_title = content.strip()

            if prop == "og:description" and content:
                self.og_description = content.strip()

            if prop == "og:type" and content:
                self.og_type = content.strip()

        elif tag == "main":
            self._main_depth += 1

        elif tag == "p" and self._main_depth:
            self._collect_p = True
            self._p_parts = []
            self._p_class = attrs.get("class", "")

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "title":
            self._in_title = False
            self.title = clean_text(" ".join(self._title_parts))

        elif tag == "p" and self._collect_p:
            text = clean_text(" ".join(self._p_parts))
            self.paragraphs.append((self._p_class, text))
            self._collect_p = False
            self._p_parts = []
            self._p_class = ""

        elif tag == "main" and self._main_depth:
            self._main_depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)

        if self._collect_p:
            self._p_parts.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def truncate_description(value: str, limit: int = 160) -> str:
    value = clean_text(value)

    if len(value) <= limit:
        return value

    shortened = value[: limit - 1]
    shortened = shortened.rsplit(" ", 1)[0].rstrip(" ,;:-")

    return shortened + "…"


def choose_description(parser: PageParser, title: str) -> tuple[str, str]:
    if parser.description:
        return truncate_description(parser.description), "existing"

    ignored_classes = {
        "eyebrow",
        "subtitle",
        "button-row",
    }

    # Prefer a meaningful explanatory paragraph rather than a tiny
    # eyebrow/subtitle/button label.
    for classes, paragraph in parser.paragraphs:
        class_set = set(classes.split())

        if class_set & ignored_classes:
            continue

        if len(paragraph) >= 70:
            return truncate_description(paragraph), "generated-from-page"

    for _, paragraph in parser.paragraphs:
        if len(paragraph) >= 40:
            return truncate_description(paragraph), "generated-from-page"

    return truncate_description(title), "title-fallback"


# ============================================================
# URL / LANGUAGE HANDLING
# ============================================================

def public_path(rel: Path) -> str:
    value = rel.as_posix()

    if value == "index.html":
        return "/"

    if value.endswith("/index.html"):
        return "/" + value[:-len("index.html")]

    return "/" + value


def absolute_url(rel: Path) -> str:
    return SITE_URL + public_path(rel)


def page_language(rel: Path, parser: PageParser) -> str:
    if parser.lang:
        lang = parser.lang.lower().split("-")[0]
        if lang in LANG_CONFIG:
            return lang

    if rel.parts and rel.parts[0] == "es":
        return "es"

    return "en"


def counterpart_for(rel: Path, all_pages: set[Path]) -> Path | None:
    if rel in SPECIAL_PAIRS:
        candidate = SPECIAL_PAIRS[rel]
        return candidate if candidate in all_pages else None

    if rel.parts and rel.parts[0] == "es":
        candidate = Path(*rel.parts[1:])
    else:
        candidate = Path("es") / rel

    return candidate if candidate in all_pages else None


def language_urls(
    rel: Path,
    lang: str,
    counterpart: Path | None,
) -> tuple[str | None, str | None]:
    own = absolute_url(rel)

    if counterpart is None:
        if lang == "en":
            return own, None
        return None, own

    other = absolute_url(counterpart)

    if lang == "en":
        return own, other

    return other, own


def choose_og_type(rel: Path, existing: str | None) -> str:
    if existing:
        return existing

    if rel.name == "book.html":
        return "book"

    if rel.name == "about.html":
        return "profile"

    return "website"


# ============================================================
# METADATA GENERATION
# ============================================================

def esc(value: str) -> str:
    return html.escape(value, quote=True)


def build_metadata(
    *,
    rel: Path,
    lang: str,
    title: str,
    description: str,
    og_title: str,
    og_description: str,
    og_type: str,
    counterpart: Path | None,
    existing_description: bool,
) -> str:

    config = LANG_CONFIG[lang]
    canonical = absolute_url(rel)

    en_url, es_url = language_urls(rel, lang, counterpart)

    lines = [
        BEGIN,
        f'<meta name="theme-color" content="{THEME_COLOR}">',
    ]

    # If the page did not already have a meta description, create one.
    if not existing_description:
        lines.append(
            f'<meta name="description" content="{esc(description)}">'
        )

    lines.extend([
        "",
        f'<link rel="canonical" href="{canonical}">',
        "",
    ])

    if en_url:
        lines.append(
            f'<link rel="alternate" hreflang="en" href="{en_url}">'
        )

    if es_url:
        lines.append(
            f'<link rel="alternate" hreflang="es" href="{es_url}">'
        )

    # x-default points to English when an English version exists.
    if en_url:
        lines.append(
            f'<link rel="alternate" hreflang="x-default" href="{en_url}">'
        )

    lines.extend([
        "",
        f'<meta property="og:site_name" content="{esc(config["site_name"])}">',
        f'<meta property="og:type" content="{esc(og_type)}">',
        f'<meta property="og:title" content="{esc(og_title)}">',
        f'<meta property="og:description" content="{esc(og_description)}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:image" content="{config["og_image"]}">',
        f'<meta property="og:image:alt" content="{esc(config["og_image_alt"])}">',
        END,
    ])

    return "\n".join(lines)


# ============================================================
# SAFE REMOVAL OF OLD SEO METADATA
# ============================================================

MANAGED_RE = re.compile(
    re.escape(BEGIN) + r".*?" + re.escape(END),
    re.I | re.S,
)

META_INCLUDE_RE = re.compile(
    r'^[ \t]*<div\s+data-include=["\']/'
    r'(?:includes|includes_es)/meta\.html["\']\s*></div>[ \t]*\n?',
    re.I | re.M,
)

THEME_RE = re.compile(
    r'\s*<meta\b(?=[^>]*\bname=["\']theme-color["\'])[^>]*>\s*',
    re.I,
)

CANONICAL_RE = re.compile(
    r'\s*<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>\s*',
    re.I,
)

ALTERNATE_RE = re.compile(
    r'\s*<link\b'
    r'(?=[^>]*\brel=["\']alternate["\'])'
    r'(?=[^>]*\bhreflang=["\'])'
    r'[^>]*>\s*',
    re.I,
)

OG_RE = re.compile(
    r'\s*<meta\b'
    r'(?=[^>]*\bproperty=["\']og:[^"\']+["\'])'
    r'[^>]*>\s*',
    re.I,
)


def remove_old_static_seo(text: str) -> str:
    text = MANAGED_RE.sub("", text)
    text = META_INCLUDE_RE.sub("", text)

    # Removes only the SEO fields managed by this script.
    # GA, fonts, CSS, scripts, JSON-LD, title, and existing description
    # are deliberately untouched.
    text = THEME_RE.sub("\n", text)
    text = CANONICAL_RE.sub("\n", text)
    text = ALTERNATE_RE.sub("\n", text)
    text = OG_RE.sub("\n", text)

    return text


def insert_after_title(text: str, metadata: str) -> str:
    title_match = re.search(
        r"</title\s*>",
        text,
        flags=re.I,
    )

    if not title_match:
        raise ValueError("No </title> found")

    pos = title_match.end()

    return (
        text[:pos]
        + "\n\n"
        + metadata
        + "\n"
        + text[pos:]
    )


# ============================================================
# PAGE DISCOVERY
# ============================================================

def discover_pages(root: Path) -> list[Path]:
    pages = []

    for path in root.rglob("*.html"):
        rel = path.relative_to(root)

        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        if path.name in SKIP_FILES:
            continue

        if path.name.endswith(".bak"):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"SKIP non-UTF8: {rel}", file=sys.stderr)
            continue

        # Respect deliberate noindex pages.
        if re.search(
            r'<meta\b(?=[^>]*name=["\']robots["\'])'
            r'(?=[^>]*content=["\'][^"\']*noindex)',
            text,
            re.I,
        ):
            continue

        if not re.search(r"<head\b", text, re.I):
            continue

        pages.append(rel)

    return sorted(pages, key=lambda p: p.as_posix())


# ============================================================
# MIGRATION
# ============================================================

def process_page(
    root: Path,
    rel: Path,
    all_pages: set[Path],
    apply: bool,
):
    path = root / rel
    original = path.read_text(encoding="utf-8")

    parser = PageParser()
    parser.feed(original)

    title = clean_text(parser.title)

    if not title:
        return {
            "status": "error",
            "page": rel,
            "message": "missing <title>",
        }

    lang = page_language(rel, parser)

    description, desc_source = choose_description(parser, title)

    og_title = parser.og_title or title
    og_description = parser.og_description or description
    og_type = choose_og_type(rel, parser.og_type)

    counterpart = counterpart_for(rel, all_pages)

    metadata = build_metadata(
        rel=rel,
        lang=lang,
        title=title,
        description=description,
        og_title=og_title,
        og_description=og_description,
        og_type=og_type,
        counterpart=counterpart,
        existing_description=bool(parser.description),
    )

    cleaned = remove_old_static_seo(original)
    updated = insert_after_title(cleaned, metadata)

    # Normalize excessive blank lines created where old tags were removed.
    updated = re.sub(r"\n{4,}", "\n\n\n", updated)

    changed = updated != original

    if apply and changed:
        path.write_text(updated, encoding="utf-8")

    return {
        "status": "changed" if changed else "unchanged",
        "page": rel,
        "lang": lang,
        "counterpart": counterpart,
        "desc_source": desc_source,
    }


# ============================================================
# VERIFICATION
# ============================================================

def count_matches(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, re.I | re.S))


def check_page(
    root: Path,
    rel: Path,
    all_pages: set[Path],
) -> list[str]:

    errors = []
    path = root / rel
    text = path.read_text(encoding="utf-8")

    parser = PageParser()
    parser.feed(text)

    expected_canonical = absolute_url(rel)

    canonicals = re.findall(
        r'<link\b(?=[^>]*rel=["\']canonical["\'])'
        r'[^>]*href=["\']([^"\']+)["\'][^>]*>',
        text,
        re.I,
    )

    if len(canonicals) != 1:
        errors.append(
            f"expected 1 canonical, found {len(canonicals)}"
        )
    elif canonicals[0] != expected_canonical:
        errors.append(
            f"canonical is {canonicals[0]}, expected {expected_canonical}"
        )

    if META_INCLUDE_RE.search(text):
        errors.append("still uses runtime meta include")

    for prop in (
        "og:site_name",
        "og:type",
        "og:title",
        "og:description",
        "og:url",
        "og:image",
        "og:image:alt",
    ):
        pattern = (
            r'<meta\b(?=[^>]*property=["\']'
            + re.escape(prop)
            + r'["\'])[^>]*>'
        )

        if count_matches(pattern, text) != 1:
            errors.append(f"{prop} missing or duplicated")

    if "titoneedsakney.com" in text:
        errors.append("contains misspelled domain titoneedsakney.com")

    lang = page_language(rel, parser)
    counterpart = counterpart_for(rel, all_pages)

    if counterpart:
        if 'hreflang="en"' not in text:
            errors.append("missing English hreflang")

        if 'hreflang="es"' not in text:
            errors.append("missing Spanish hreflang")

        if 'hreflang="x-default"' not in text:
            errors.append("missing x-default hreflang")

    # This should remain true for normal site pages.
    if "G-JHT0DBJBHH" not in text:
        errors.append("Google Analytics ID missing")

    return errors


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate static SEO metadata for the Tito Needs a Kidney site."
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to HTML files.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify metadata after migration.",
    )

    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    pages = discover_pages(root)
    all_pages = set(pages)

    if args.check:
        failures = 0

        for rel in pages:
            errors = check_page(root, rel, all_pages)

            if errors:
                failures += 1
                print(f"FAIL: {rel}")

                for error in errors:
                    print(f"  - {error}")

        if failures:
            print()
            print(f"{failures} page(s) failed metadata checks.")
            return 1

        print(f"PASS: {len(pages)} standalone HTML pages checked.")
        return 0

    apply = args.apply

    changed = 0
    unchanged = 0
    generated_desc = []
    no_translation = []
    errors = []

    print(
        "APPLY MODE" if apply else "DRY RUN — no files will be changed"
    )
    print()

    for rel in pages:
        try:
            result = process_page(
                root,
                rel,
                all_pages,
                apply,
            )
        except Exception as exc:
            errors.append((rel, str(exc)))
            print(f"ERROR: {rel}: {exc}")
            continue

        if result["status"] == "changed":
            changed += 1
            prefix = "UPDATED" if apply else "WOULD UPDATE"
            print(f"{prefix}: {rel}")
        else:
            unchanged += 1

        if result.get("desc_source") != "existing":
            generated_desc.append(
                (rel, result.get("desc_source"))
            )

        if result.get("counterpart") is None:
            no_translation.append(rel)

    print()
    print(f"Pages discovered: {len(pages)}")
    print(f"Pages {'updated' if apply else 'that would change'}: {changed}")
    print(f"Unchanged: {unchanged}")

    if generated_desc:
        print()
        print("Descriptions generated from visible page content:")
        for rel, source in generated_desc:
            print(f"  {rel}  [{source}]")

    if no_translation:
        print()
        print("Pages with no matching translation file:")
        for rel in no_translation:
            print(f"  {rel}")

    if errors:
        print()
        print("ERRORS:")
        for rel, error in errors:
            print(f"  {rel}: {error}")
        return 1

    if not apply:
        print()
        print("Dry run complete.")
        print("Review the list, then run:")
        print("  python3 scripts/update_static_metadata.py --apply")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
