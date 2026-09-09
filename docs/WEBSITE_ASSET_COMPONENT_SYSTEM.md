# Website Asset and Component System

**Status:** Foundation  
**Goal:** Make `titoneedsakidney.com` increasingly buildable from durable reusable parts without sacrificing page-specific SEO, bilingual parity, accessibility, or static-site simplicity.

The website is a sales/distribution surface for *Tito Needs a Kidney*. This document defines reusable website construction assets ("Legos") and how they relate to the shared publishing asset system.

## Core rule

Reuse **structure, facts, components, and controlled content fragments**. Keep **search intent, public URL, title tag, H1, page introduction, surrounding prose, internal-link context, and context-specific alt text** page-specific when needed.

Internal stable names are implementation details. They must not force repetitive public SEO text.

## Three layers

### 1. Shared publishing assets

Canonical facts and media used by both website and outreach belong to the shared publishing asset layer in `TitoNeedsAKidney.Research`, including:

- edition/format metadata
- ISBN/ASIN and other identifiers after verification
- canonical book covers/master media
- approved author facts
- approved reusable descriptions/bios
- retailer/distributor availability evidence
- library availability evidence
- durable reviews/placements when registered

The website may keep optimized derivatives locally (for example responsive WebP cover sizes), but they should resolve to one logical source asset rather than becoming separate semantic facts.

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

## Known first extraction candidate: book page

Current `book.html` already contains several reusable concepts:

- shared header/navigation
- language switcher
- responsive English cover derivatives
- book hero
- retailer/purchase CTA block
- verified availability section
- Book JSON-LD
- reusable book description/facts

The current live page should remain unchanged during the foundation phase. The first implementation pass should extract data/structure only after parity tests can prove that generated or included output preserves:

- current URLs
- canonical/hreflang behavior
- structured data
- analytics attributes
- accessibility semantics
- visible content
- static rendering

## Asset binding model

Website-specific bindings map local optimized files or components to shared logical publishing assets.

Example:

```json
{
  "publishing_asset_id": "TNK-MEDIA-COVER-EN-FRONT",
  "derivatives": [
    "/assets/images/book-cover-en-320.webp",
    "/assets/images/book-cover-en-520.webp",
    "/assets/images/book-cover-en-800.webp"
  ]
}
```

This lets the website optimize delivery without pretending each rendered size is a different content asset.

## SEO boundaries

Reusable construction is compatible with SEO when these remain deliberate and page-specific:

- canonical URL
- title tag
- H1
- meta description
- intro/body copy where search intent differs
- internal anchor context
- schema values that differ by edition/page
- image alt text when context changes

Do not create thin pages by combining a template with only a swapped noun/location/category. A page must have a real audience/search purpose and enough unique useful content to justify indexing.

## Bilingual parity

English and Spanish pages may share patterns/components but must preserve language-specific:

- copy
- metadata
- hreflang relationships
- edition facts
- retailer/library claims
- CTAs
- structured data

Do not infer Spanish edition availability from English distribution evidence or vice versa.

## Build direction

Stay static-first. The preferred evolution is:

`structured data + small templates/includes -> generated static HTML -> GitHub Pages`

Do not introduce a framework merely to gain component reuse. A minimal build step is preferable if it can preserve the current static output and repository checks.

## Migration sequence

1. Register shared publishing assets.
2. Inventory repeated website structures and local media derivatives.
3. Add website binding/manifests without changing rendered pages.
4. Extract one low-risk component or page pattern and prove byte/semantic parity where practical.
5. Add regression checks for SEO metadata, hreflang, analytics hooks, accessibility, and required content.
6. Migrate touched pages opportunistically rather than rewriting the entire site at once.
7. Only after repeated patterns are proven should the build step become the normal authoring path.

## Success condition

A worker should be able to create or revise a page by selecting approved publishing assets, a known page pattern, and reusable components while still writing the unique SEO/content layer for that page. A change to a canonical cover, author fact, or verified edition field should have one controlled source and predictable downstream consumers.
