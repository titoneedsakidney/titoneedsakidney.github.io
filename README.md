# Tito Needs a Kidney

Source for the bilingual static site at [titoneedsakidney.com](https://titoneedsakidney.com).

## Local validation

The site has no build-time application dependencies. Python and Node.js are used for
content generation, integrity checks, and tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/check_site_integrity.py
node tests/test_analytics_loader.js
node tests/test_analytics.js
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete release checks, including
regenerating shared includes, metadata, structured data, and the sitemap.

## Repository structure

- `includes/` and `includes_es/`: shared English and Spanish page components
- `scripts/`: generation, integrity, analytics, and audit utilities
- `tests/`: Python and Node.js regression tests
- `assets/`: static images, styles, and scripts
- `docs/`: operational and analytics documentation

Preserve English/Spanish parity and the canonical, hreflang, privacy, and claim
boundaries documented in `AGENTS.md` when changing public content.
