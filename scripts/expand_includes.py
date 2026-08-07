#!/usr/bin/env python3

from pathlib import Path
import argparse
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

BEGIN_RE = re.compile(
    r'<!-- STATIC INCLUDE: (?P<path>/[^ ]+) BEGIN -->'
    r'.*?'
    r'<!-- STATIC INCLUDE: (?P=path) END -->',
    re.S,
)

PLACEHOLDER_RE = re.compile(
    r'<div\s+data-include=["\'](?P<path>/[^"\']+)["\']\s*>\s*</div>',
    re.I,
)

INCLUDE_SCRIPT_RE = re.compile(
    r'^[ \t]*<script\s+src=["\']/scripts/include\.js["\']'
    r'(?:\s+defer)?\s*></script>[ \t]*\n?',
    re.I | re.M,
)


def resolve_include(url_path: str) -> Path:
    if not url_path.startswith("/"):
        raise ValueError(f"Include path must be root-relative: {url_path}")

    candidate = (ROOT / url_path.lstrip("/")).resolve()

    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        raise ValueError(f"Include escapes repository root: {url_path}")

    if not candidate.is_file():
        raise FileNotFoundError(f"Missing include: {url_path}")

    return candidate


def expand_fragment(url_path: str, stack=None) -> str:
    stack = list(stack or [])

    if url_path in stack:
        chain = " -> ".join(stack + [url_path])
        raise ValueError(f"Recursive include detected: {chain}")

    stack.append(url_path)

    path = resolve_include(url_path)
    text = path.read_text(encoding="utf-8").strip()

    # Support nested includes if they ever exist.
    def replace_nested(match):
        nested = match.group("path")
        content = expand_fragment(nested, stack)
        return (
            f'<!-- STATIC INCLUDE: {nested} BEGIN -->\n'
            f'{content}\n'
            f'<!-- STATIC INCLUDE: {nested} END -->'
        )

    text = PLACEHOLDER_RE.sub(replace_nested, text)

    return text


def render_include(url_path: str) -> str:
    content = expand_fragment(url_path)

    return (
        f'<!-- STATIC INCLUDE: {url_path} BEGIN -->\n'
        f'{content}\n'
        f'<!-- STATIC INCLUDE: {url_path} END -->'
    )


def refresh_existing_blocks(text: str) -> tuple[str, int]:
    count = 0

    def repl(match):
        nonlocal count
        count += 1
        return render_include(match.group("path"))

    return BEGIN_RE.sub(repl, text), count


def expand_placeholders(text: str) -> tuple[str, int]:
    count = 0

    def repl(match):
        nonlocal count
        count += 1
        return render_include(match.group("path"))

    return PLACEHOLDER_RE.sub(repl, text), count


def discover_pages():
    pages = []

    for path in ROOT.rglob("*.html"):
        rel = path.relative_to(ROOT)

        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        if path.name == "404.html":
            continue

        pages.append(path)

    return sorted(pages)


def process(path: Path, apply=False):
    original = path.read_text(encoding="utf-8")

    text, refreshed = refresh_existing_blocks(original)
    text, expanded = expand_placeholders(text)

    remaining = PLACEHOLDER_RE.findall(text)

    if remaining:
        raise ValueError(
            f"{path.relative_to(ROOT)} still contains "
            f"{len(remaining)} runtime include(s)"
        )

    # include.js is no longer needed once every fragment is static.
    text = INCLUDE_SCRIPT_RE.sub("", text)

    changed = text != original

    if apply and changed:
        path.write_text(text, encoding="utf-8")

    return changed, refreshed, expanded


def check():
    failures = 0
    pages = discover_pages()

    for path in pages:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")

        if PLACEHOLDER_RE.search(text):
            print(f"FAIL: runtime include remains: {rel}")
            failures += 1

        if "/scripts/include.js" in text:
            print(f"FAIL: include.js still loaded: {rel}")
            failures += 1

        # Every generated marker must have a matching end marker.
        begins = re.findall(
            r'<!-- STATIC INCLUDE: (/[^ ]+) BEGIN -->',
            text
        )
        ends = re.findall(
            r'<!-- STATIC INCLUDE: (/[^ ]+) END -->',
            text
        )

        if begins != ends:
            print(f"FAIL: mismatched include markers: {rel}")
            failures += 1

    if failures:
        print()
        print(f"{failures} failure(s).")
        return 1

    print(f"PASS: {len(pages)} standalone HTML pages use static includes.")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.apply and args.check:
        print("Use either --apply or --check.")
        return 1

    if args.check:
        return check()

    pages = discover_pages()

    changed = 0
    expanded_total = 0
    refreshed_total = 0

    print(
        "APPLY MODE"
        if args.apply
        else "DRY RUN — no files will be changed"
    )
    print()

    for path in pages:
        rel = path.relative_to(ROOT)

        try:
            did_change, refreshed, expanded = process(
                path,
                apply=args.apply,
            )
        except Exception as exc:
            print(f"ERROR: {rel}: {exc}")
            return 1

        refreshed_total += refreshed
        expanded_total += expanded

        if did_change:
            changed += 1
            action = "UPDATED" if args.apply else "WOULD UPDATE"
            print(
                f"{action}: {rel} "
                f"(new={expanded}, refreshed={refreshed})"
            )

    print()
    print(f"Standalone pages: {len(pages)}")
    print(f"Pages {'updated' if args.apply else 'that would change'}: {changed}")
    print(f"New placeholders expanded: {expanded_total}")
    print(f"Existing generated includes refreshed: {refreshed_total}")

    if not args.apply:
        print()
        print("Dry run only. To apply:")
        print("  python3 scripts/expand_includes.py --apply")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
