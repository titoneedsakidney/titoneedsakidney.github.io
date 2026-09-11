# Deterministic GA4 page-transition report

## Purpose

Issue #27's remaining Phase 2 reporting gap is aggregate next-page evidence. This helper replaces repeated manual/AI inspection of page/referrer rows with a deterministic, privacy-bounded reducer.

It consumes an **aggregate** GA4 CSV containing only:

- `hostName`
- `pageReferrer`
- `pagePath`
- `screenPageViews`

It does not query GA4, identify visitors, reconstruct user-level sessions, or write anything back to Analytics. The input and generated report remain private operational evidence unless separately redacted for publication.

## Input contract

Create the aggregate report for the desired date window with dimensions:

```text
hostName
pageReferrer
pagePath
```

and metric:

```text
screenPageViews
```

Keep the export outside this public repository. Do not add user/session identifiers, raw event rows, email addresses, CRM data, or recipient-level campaign data. The tool fails closed if known visitor/session identifier columns such as `userPseudoId`, `userId`, `clientId`, or session IDs are present.

`hostName` is required so copied/local/foreign-host traffic can be excluded deterministically. Current-page rows are counted only when `hostName` is exactly `titoneedsakidney.com`.

## Run

```bash
python3 scripts/summarize_ga4_transitions.py \
  --input /secure/path/ga4-page-referrer.csv \
  --json-output /secure/path/ga4-page-transitions.json \
  --markdown-output /secure/path/ga4-page-transitions.md
```

The default display thresholds are three page views and three observed transition views. They reduce low-volume noise; they are **not** a privacy guarantee or statistical-significance rule. Change them only for a specific analysis need:

```bash
python3 scripts/summarize_ga4_transitions.py \
  --input /secure/path/ga4-page-referrer.csv \
  --min-page-views 5 \
  --min-transition-views 5 \
  --top 30
```

If neither output path is supplied, JSON is printed to stdout.

## What it reports

The reducer:

- ignores current-page rows from non-production hosts;
- normalizes `/index.html` and nested `/index.html` paths to the site's canonical trailing-slash convention;
- strips query strings/fragments from same-site referrers before path comparison;
- separates direct/external-referrer views from same-site transitions;
- separates same-page referrer/reload views from page-to-page transitions;
- ranks observed same-site transitions deterministically;
- produces a cautious review queue of pages with traffic but no observed same-site next page;
- emits stable JSON (`tnk-ga4-page-transitions-v1`) for later ordinary-software consumption.

## Interpretation boundary

`pageReferrer` is directional aggregate evidence, not a visitor-level path ledger. A page with no observed same-site next page is **not automatically an exit or a dead end**. The visit may have ended, gone to an external destination, lost referrer information, or simply had too little traffic.

Do not compute person-level funnels, identify organizations/recipients, or claim causality from this report. It complements GA4's aggregate entry/event/device/language reporting; it does not replace Analytics exploration when richer authenticated evidence is available.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_summarize_ga4_transitions.py' -v
```

The focused tests cover production-host filtering, canonical path normalization, direct/external/referrer classification, reload separation, minimum-count display suppression, visitor-identifier rejection, invalid aggregate counts, and cautious report wording.

## Adoption state

**Source-ready.** Unit tests and a synthetic CLI smoke test are sufficient to validate the reducer itself. Live proof still requires one current private aggregate export in the four-column input shape. Do not fabricate production analytics rows merely to exercise the tool.
