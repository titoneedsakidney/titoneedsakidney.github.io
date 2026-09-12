# Deterministic Search Console opportunity reducer

Issue #27 requires a low-manual-work aggregate report that includes Search
Console queries, impressions, clicks, CTR, and a reproducible handoff to the
search-opportunity audit in Issue #21. `scripts/summarize_search_console.py`
moves the repetitive candidate-selection step into ordinary offline software.

## Boundary

The reducer is read-only. It does not call Google, alter Search Console or GA4,
change the site, or make an SEO decision. It accepts an aggregate CSV that was
already exported through an approved private workflow.

Raw Search Console query text is private evidence. By default the reducer does
**not** echo it. Each query is represented by a stable 16-character SHA-256
fingerprint so repeated aggregate candidates can be compared without copying
private search text into a public Issue or PR. Use `--include-query-text` only
for private local review, and keep that output outside this repository.

The tool rejects common visitor/session identifier columns. It also strips
hosts, query strings, and fragments from an optional page dimension before
reporting it.

## Accepted CSV shape

Header matching is case-insensitive and tolerates the usual Search Console
labels such as `Query` / `Top queries`, `Page` / `Top pages`, and
`Position` / `Average position`.

Required dimensions/metrics:

- query;
- clicks;
- impressions;
- average position.

Optional:

- page;
- CTR.

CTR is validated when present, but the reducer recomputes CTR from
clicks/impressions so export-display rounding cannot change the result.

## Run it

Privacy-safe JSON:

```bash
python scripts/summarize_search_console.py \
  /private/path/search-console.csv \
  --window-start 2026-09-01 \
  --window-end 2026-09-07
```

Privacy-safe Markdown:

```bash
python scripts/summarize_search_console.py \
  /private/path/search-console.csv \
  --window-start 2026-09-01 \
  --window-end 2026-09-07 \
  --format markdown
```

Private local review with query text:

```bash
python scripts/summarize_search_console.py \
  /private/path/search-console.csv \
  --window-start 2026-09-01 \
  --window-end 2026-09-07 \
  --include-query-text \
  --output /private/path/search-console-review.json
```

The default review filter is:

- at least 25 impressions;
- CTR no greater than 5%;
- average position no worse than 10.

Those are **review filters, not diagnoses**. Override them with
`--min-impressions`, `--max-ctr`, and `--max-position` when a different
observation window or decision question warrants it. Inclusion never proves
that metadata, content, or navigation is defective.

## Output contract

The JSON report records:

- schema version and `FACTS_READY` state;
- observation window when supplied;
- exact review-filter values;
- aggregate row/click/impression counts;
- whether a page dimension was available;
- redacted candidate rows sorted deterministically;
- page-level candidate counts/impressions when page data exists;
- the interpretation boundary.

No automatic content change follows from this output. Issue #21 still owns the
evidence-backed diagnosis of high-impression, low-click pages, and private query
evidence must be summarized by intent rather than pasted publicly.

## Verification

Focused offline tests:

```bash
python -m unittest -v tests.test_summarize_search_console
```

The tests use synthetic data only. A real private-export smoke should use the
privacy-safe default first and confirm that the output contains no raw query
text before the result is used in any public handoff.
