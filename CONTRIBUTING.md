# Release checks

Before pushing a static-site change, regenerate shared includes and generated metadata,
then run the complete local release check:

```bash
python3 scripts/expand_includes.py --apply
python3 scripts/update_static_metadata.py --apply
python3 scripts/update_structured_data.py --apply
python3 scripts/generate_sitemap.py
python3 scripts/check_site_integrity.py
git diff --check
```

`check_site_integrity.py` also runs the static-include, metadata, structured-data, and
sitemap freshness checks. It checks deployable standalone pages for document landmarks,
skip links, language/canonical/hreflang pairing, internal links and fragments, JSON-LD,
runtime include placeholders, and accidental duplicate visible main content.

If two intentionally different pages must retain identical visible main content, add their
two repository-relative paths to `duplicate_visible_bodies` in
`scripts/integrity_allowlist.json` and explain the exception in the pull request.
