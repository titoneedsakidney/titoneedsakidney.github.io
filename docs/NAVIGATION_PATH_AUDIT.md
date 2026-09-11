# Deterministic navigation path audit

## Purpose

`scripts/audit_navigation_paths.py` replaces repeated manual/AI inspection of "how many clicks does it take to reach each page?" with ordinary deterministic software.

It is intentionally read-only. It does not call Google Analytics, Search Console, the public site, or any other network service. It analyzes the committed static HTML graph using the same page discovery, parser, and internal-link resolver used by `scripts/check_site_integrity.py`.

This is a topology audit, not a popularity report. GA4 still owns actual visitor behavior; this tool answers whether pages are linked and how many internal clicks separate them from a chosen entry page.

## Run it

From the repository root:

```bash
python scripts/audit_navigation_paths.py
```

The default entry point is `index.html`. For bilingual comparison:

```bash
python scripts/audit_navigation_paths.py \
  --start index.html \
  --start es/index.html
```

For a machine-readable artifact:

```bash
python scripts/audit_navigation_paths.py \
  --start index.html \
  --start es/index.html \
  --json-output /tmp/tnk-navigation-paths.json
```

Use `--json` to print the complete report to stdout.

## Report contract

Schema: `tnk-site-navigation-paths-v1`.

The report contains:

- total standalone page count;
- total directed internal page-to-page link count;
- pages with zero incoming internal links;
- pages with zero outgoing internal page links;
- for each entry page: reachable/unreachable counts, mean/median/max click distance, click-distance histogram, longest-distance pages, and one deterministic shortest path to every reachable page.

The shortest-path calculation uses breadth-first search. Repeated links and self-links do not inflate the graph. External links, non-HTML assets, and pages excluded by the existing site-integrity discovery contract are ignored.

## Safety and interpretation

- Read-only and network-free.
- No analytics identifiers or visitor data.
- No automatic navigation changes or thresholds are imposed. A high click count is evidence for design review, not an automatic defect.
- An unreachable standalone page is worth review, but may still be intentional if it is meant to be reached only from an external campaign. Use the page's intended role before changing navigation.
- Because the tool reuses `check_site_integrity.py`, link resolution stays aligned with the release validator rather than creating a second URL interpretation.

## Validation

Focused unit tests:

```bash
python -m unittest discover -s tests -p 'test_audit_navigation_paths.py' -v
```

A source-level smoke test against current site HTML is:

```bash
python scripts/audit_navigation_paths.py --start index.html --start es/index.html --json
```

The source change does not add a scheduler, dispatcher, public analytics call, or deployment behavior. It is ready to be invoked manually or by an existing approved local/repository validation lane later.
