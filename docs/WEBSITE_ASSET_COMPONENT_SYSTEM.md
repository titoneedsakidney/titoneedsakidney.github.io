# Website Asset and Component System

**Status:** Foundation  
**Goal:** Make `titoneedsakidney.com` increasingly buildable from durable reusable parts without sacrificing page-specific SEO, bilingual parity, accessibility, privacy, or static-site simplicity.

The website is a sales/distribution surface for *Tito Needs a Kidney*. This document defines reusable website construction assets ("Legos") and how they relate to the existing controlled publishing assets.

## Core rule

Reuse **structure, canonical facts, components, and controlled content fragments**. Keep **search intent, public URL, title tag, H1, page introduction, surrounding prose, internal-link context, and context-specific alt text** page-specific when needed.

Internal stable names are implementation details. They must not force repetitive public SEO text.

## Canonical publishing source

The website must not create its own competing publishing registry.

Shared publishing asset identity is owned by the private **TNK Publishing Asset Catalog** and the A12 metadata/distribution infrastructure governance in `TitoNeedsAKidney.Research`. The public website repository should consume only stable logical asset IDs and approved public facts; it must not publish private provider locators merely so a worker can find the authoritative source.

Examples of existing canonical logical IDs observed 2026-09-09 include:

- `PUB-EN-INTERIOR-001`
- `PUB-EN-COVER-FRONT-001`
- `PUB-EN-REVIEW-001`
- `PUB-ES-INTERIOR-001`
- `PUB-ES-REVIEW-001`

Website bindings should reference those existing IDs when a canonical mapping exists. If no mapping exists, record the local asset as unmapped; do not invent a substitute publishing ID.

### Public-repository privacy boundary

Do not place private-system identifiers or locators in this public repository unless they are intentionally public content. In particular, website manifests and documentation should not contain private:

- Google Sheet IDs;
- Google Drive file IDs or private Drive URLs;
- CRM row/contact identifiers;
- Gmail/message identifiers;
- recipient or organization tracking identifiers.

The private Research integration layer may retain provider locators where needed for controlled resolution. The website should normally need only the logical `PUB-*` identity and public-facing values/assets.

## Three layers

### 1. Shared publishing assets

Canonical facts and media used by both website and outreach belong to the existing Publishing Asset Catalog, including:

- controlled manuscript/interior/cover/review-copy assets;
- canonical file locations and source relationships;
- sharing and approval rules;
- edition/format metadata when registered;
- retailer/distributor availability evidence;
- other A12 publishing infrastructure.

The website may keep optimized derivatives locally (for example responsive WebP cover sizes), but they should resolve to one canonical source asset when that relationship is known.

### 2. Website components

Components are reusable presentation/building blocks. Initial target component IDs:

- `TNK-WEB-CMP-HEADER`
- `TNK-WEB-CMP-FOOTER`
- `TNK-WEB-CMP-LANGUAGE-SWITCHER`
- `TNK-WEB-CMP-BOOK-HERO`
- `TNK-WEB-CMP-BOOK-CARD`
- `TNK-WEB-CMP-REVIEW-CARD`
- `TNK-WEB-CMP-AUTHOR-BOX`
- `TNK-WEB-CMP-RETAILER-LINKS`
- `TNK-WEB-CMP-RESOURCE-CARD`
- `TNK-WEB-CMP-BREADCRUMBS`
- `TNK-WEB-CMP-CTA`

A component ID identifies behavior/structure, not visible wording.

### 3. Page manifests/patterns

A page manifest describes what a page is, which components it uses, and which fields must remain unique.

Initial pattern IDs:

- `TNK-WEB-PAT-BOOK`
- `TNK-WEB-PAT-RESOURCE-LANDING`
- `TNK-WEB-PAT-ARTICLE`
- `TNK-WEB-PAT-PROFESSIONAL`
- `TNK-WEB-PAT-TESTIMONIAL`

A pattern may be shared across English and Spanish pages without sharing SEO-critical strings.

## Minimum page manifest contract

A future manifest should support at least:

- `page_id`
- `path`
- `language`
- `pattern_id`
- `components`
- `publishing_asset_refs`
- `seo.title`
- `seo.description`
- `seo.canonical`
- `seo.hreflang`
- `seo.intent`
- `content.h1`
- page-specific content/section references

Public text should never be generated solely from the internal component or asset name.

## Known first extraction candidate: book pages

Current `/book.html` and `/es/book.html` already contain several reusable concepts:

- shared header/navigation;
- language switcher;
- responsive cover derivatives;
- book hero;
- retailer/purchase CTA block;
- verified-availability section;
- Book JSON-LD;
- reusable book description/facts.

The current live pages should remain unchanged during the foundation phase. The first implementation pass should extract data/structure only after parity tests can prove that generated or included output preserves:

- current URLs;
- canonical/hreflang behavior;
- structured data;
- analytics attributes;
- accessibility semantics;
- visible content;
- static rendering.

## Asset binding model

Website-specific bindings map local optimized files to canonical publishing assets without turning delivery variants into new publishing identities.

Known English mapping:

```json
{
  "publishing_asset_id": "PUB-EN-COVER-FRONT-001",
  "full_resolution_site_alias": "/assets/images/og-default.png",
  "derivatives": [
    "/assets/images/book-cover-en-320.webp",
    "/assets/images/book-cover-en-520.webp",
    "/assets/images/book-cover-en-800.webp"
  ]
}
```

`/assets/images/og-default.png` was verified on 2026-09-09 to be byte-identical to canonical `PUB-EN-COVER-FRONT-001`. The responsive English WebPs remain delivery derivatives of that logical asset.

For Spanish, Git history establishes `/assets/images/og-spanish.png` as the full-resolution book image used before the responsive `/assets/images/book-cover-es-{320,520,800}.webp` variants replaced it on the Spanish book/home pages. That establishes a high-confidence site-local source chain, but the private canonical catalog still has no Spanish front-cover-image master equivalent to `PUB-EN-COVER-FRONT-001`. Therefore the Spanish website binding remains canonically unmapped; do not mint a `PUB-*` identity from website history alone.

## SEO boundaries

Reusable construction is compatible with SEO when these remain deliberate and page-specific:

- canonical URL;
- title tag;
- H1;
- meta description;
- intro/body copy where search intent differs;
- internal anchor context;
- schema values that differ by edition/page;
- image alt text when context changes.

Do not create thin pages by combining a template with only a swapped noun/location/category. A page must have a real audience/search purpose and enough unique useful content to justify indexing.

## Bilingual parity

English and Spanish pages may share patterns/components but must preserve language-specific:

- copy;
- metadata;
- hreflang relationships;
- edition facts;
- retailer/library claims;
- CTAs;
- structured data.

Do not infer Spanish edition availability from English evidence or vice versa. Distribution claims must come from the canonical distribution source or stronger direct evidence.

## Build direction

Stay static-first. The preferred evolution is:

`structured data + small templates/includes -> generated static HTML -> GitHub Pages`

Do not introduce a framework merely to gain component reuse. A minimal build step is preferable if it can preserve the current static output and repository checks.

## Migration sequence

1. Bind current website assets to existing canonical `PUB-*` assets where mappings are proven.
2. Inventory repeated website structures and unmapped local media.
3. Add website binding/manifests without changing rendered pages.
4. Reconcile unmapped high-value media back into the canonical catalog before treating them as shared publishing assets.
5. Extract one low-risk component or page pattern and prove semantic parity.
6. Add regression checks for SEO metadata, hreflang, analytics hooks, accessibility, and required content.
7. Migrate touched pages opportunistically rather than rewriting the entire site at once.
8. Only after repeated patterns are proven should the build step become the normal authoring path.

## Success condition

A worker should be able to create or revise a page by selecting approved canonical publishing assets, a known page pattern, and reusable components while still writing the unique SEO/content layer for that page. A change to a canonical cover or verified edition field should have one controlled source and predictable downstream consumers, without leaking private-system locators into the public site repository.
