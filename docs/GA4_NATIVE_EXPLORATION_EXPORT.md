# Native GA4 Exploration export adapter

## Why this exists

The deterministic page-transition reducer in `scripts/summarize_ga4_transitions.py` intentionally has a narrow canonical four-column input contract. A native Google Analytics 4 Exploration CSV adds transport-only details that do not belong in the reducer's analysis semantics:

- metadata comment lines beginning with `#`;
- display-friendly headers such as `Hostname`, `Page referrer`, `Page path + query string`, and `Views`;
- a GA4 `Grand total` row with an extra cell.

Previously, a human or AI had to strip those details and rename the four fields before the reducer could run. `scripts/summarize_ga4_exploration_export.py` makes that normalization deterministic and keeps the existing reducer as the single owner of transition semantics.

## Privacy and safety boundary

The adapter remains aggregate-only and offline. It does not query Google Analytics, identify visitors, reconstruct sessions, or write anything back to GA4.

It accepts only the aggregate host/referrer/page/views shape and fails closed when known visitor/session identifier columns are present. Unexpected extra columns also fail closed; the only tolerated extra-cell row is the recognizable GA4 Exploration `Grand total` row.

Keep native exports and generated reports outside this public repository.

## Direct native-export command

```bash
python3 scripts/summarize_ga4_exploration_export.py \
  --input /secure/path/download.csv \
  --json-output /secure/path/ga4-page-transitions.json \
  --markdown-output /secure/path/ga4-page-transitions.md
```

The adapter recognizes both GA4 display labels and the reducer's canonical/API-style field labels. It then delegates path normalization, production-host filtering, low-count display thresholds, transition classification, JSON schema, and Markdown rendering to `summarize_ga4_transitions.py`.

No intermediate normalized CSV is required.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_summarize_ga4_exploration_export.py' -v
python3 -m unittest discover -s tests -p 'test_summarize_ga4_transitions.py' -v
```

Coverage includes GA4 metadata comments, friendly headers, the malformed-width Grand total row, canonical headers, visitor-identifier rejection, and fail-closed handling of unexpected extra columns.

## Adoption state

**Source-ready.** The bounded purpose is to remove the manual normalization step exposed by the first private GA4 live proof. A private native-export smoke should be run before treating the adapter itself as live-proven; no private GA4 rows belong in GitHub.
