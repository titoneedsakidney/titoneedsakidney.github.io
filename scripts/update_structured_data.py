#!/usr/bin/env python3

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://titoneedsakidney.com"

BEGIN = "<!-- GENERATED STRUCTURED DATA: BEGIN -->"
END = "<!-- GENERATED STRUCTURED DATA: END -->"


SCHEMAS = {
    Path("index.html"): {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{SITE}/#website",
        "url": f"{SITE}/",
        "name": "Tito Needs a Kidney",
        "inLanguage": "en",
        "about": {
            "@type": "Book",
            "@id": f"{SITE}/book.html#book"
        },
        "author": {
            "@type": "Person",
            "@id": f"{SITE}/about.html#person"
        }
    },

    Path("es/index.html"): {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{SITE}/es/#website",
        "url": f"{SITE}/es/",
        "name": "Tito Necesita un Riñón",
        "inLanguage": "es",
        "about": {
            "@type": "Book",
            "@id": f"{SITE}/es/book.html#book"
        },
        "author": {
            "@type": "Person",
            "@id": f"{SITE}/es/about.html#person"
        }
    },

    Path("about.html"): {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": f"{SITE}/about.html#person",
        "name": "Tito",
        "url": f"{SITE}/about.html"
    },

    Path("es/about.html"): {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": f"{SITE}/es/about.html#person",
        "name": "Tito",
        "url": f"{SITE}/es/about.html"
    }
}


def strip_generated(text):
    return re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END) + r"\s*",
        "",
        text,
        flags=re.S
    )


def render(schema):
    return (
        BEGIN + "\n"
        '<script type="application/ld+json">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>\n"
        + END
    )


def update_page(rel, apply=False):
    path = ROOT / rel

    if not path.exists():
        raise FileNotFoundError(rel)

    original = path.read_text(encoding="utf-8")
    cleaned = strip_generated(original)

    if "</head>" not in cleaned:
        raise ValueError(f"{rel}: missing </head>")

    block = render(SCHEMAS[rel])

    updated = cleaned.replace(
        "</head>",
        block + "\n</head>",
        1
    )

    changed = updated != original

    if apply and changed:
        path.write_text(updated, encoding="utf-8")

    return changed


def check():
    failures = 0

    for rel in SCHEMAS:
        path = ROOT / rel

        if not path.exists():
            print(f"FAIL: missing {rel}")
            failures += 1
            continue

        text = path.read_text(encoding="utf-8")

        if text.count(BEGIN) != 1:
            print(f"FAIL: {rel}: generated block count != 1")
            failures += 1
            continue

        match = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            text,
            flags=re.S
        )

        if not match:
            print(f"FAIL: {rel}: JSON-LD missing")
            failures += 1
            continue

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            print(f"FAIL: {rel}: invalid JSON: {exc}")
            failures += 1
            continue

        expected = SCHEMAS[rel]

        if data != expected:
            print(f"FAIL: {rel}: generated schema differs from expected")
            failures += 1

    if failures:
        print(f"\n{failures} failure(s).")
        return 1

    print("PASS: WebSite and Person structured data verified.")
    return 0


def main():
    apply = "--apply" in sys.argv
    do_check = "--check" in sys.argv

    if apply and do_check:
        print("Use either --apply or --check.")
        return 1

    if do_check:
        return check()

    print("APPLY MODE" if apply else "DRY RUN — no files will be changed")
    print()

    changed = 0

    for rel in SCHEMAS:
        try:
            did_change = update_page(rel, apply=apply)
        except Exception as exc:
            print(f"ERROR: {rel}: {exc}")
            return 1

        if did_change:
            changed += 1
            print(
                f"{'UPDATED' if apply else 'WOULD UPDATE'}: {rel}"
            )

    print()
    print(f"Pages that would change: {changed}" if not apply else f"Pages updated: {changed}")

    if not apply:
        print()
        print("If this looks right, run:")
        print("  python3 scripts/update_structured_data.py --apply")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
