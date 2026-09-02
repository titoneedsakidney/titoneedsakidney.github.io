# Campaign Attribution Contract

**Control date:** 2026-09-02  
**Scope:** public website behavior for inbound campaign links.

## Goal

Allow privacy-bounded campaign attribution from Tito Needs a Kidney first-contact outreach into GA4 while keeping the public site free of person-level tracking and private outreach data.

## Incoming outreach URL pattern

First-contact email links may arrive with:

```text
utm_source=organization-outreach
utm_medium=email
utm_campaign=cmp-XX
utm_content=first-contact-<placement>-<language>-v1
```

`cmp-XX` identifies only a campaign cohort. It never identifies a recipient, organization, contact, message, or CRM row.

The public site must accept ordinary UTM query parameters without breaking the requested page or stripping them before GA4 can attribute the landing session.

## Privacy rules

Do not add or expose:

- recipient-unique URLs;
- open-tracking pixels;
- hidden redirect tracking;
- person/contact/organization IDs;
- CRM IDs or Gmail IDs;
- custom browser fingerprints;
- UTM persistence in local storage or public profile records;
- visitor-to-CRM matching.

Do not copy private analytics exports or CRM data into this public repository.

## URL behavior

- Canonical public origin remains `https://titoneedsakidney.com`.
- Incoming UTM parameters may exist on the landing URL.
- Do **not** propagate the UTM query onto normal internal links. GA4 session campaign attribution should persist without polluting internal URLs.
- Canonical tags and hreflang must continue to point to clean canonical URLs without campaign query parameters.
- Language switching must continue to work from a UTM-tagged landing page.
- No campaign-specific redirect page is required merely for attribution.

## Semantic events

Preserve the existing semantic analytics layer in `scripts/analytics.js`:

- `start_help_flow`
- `browse_organizations`
- `view_book`
- `outbound_purchase`

These events are interpreted under the inbound GA4 session campaign. Do not duplicate UTM values into custom event parameters solely to make attribution work.

If website work adds new meaningful CTA classes, use stable non-personal action IDs and preserve bilingual parity.

## Landing-role implementation

Website work should keep a stable map for outreach-capable destinations such as:

- English general/home;
- Spanish general/home;
- English book information;
- Spanish book information;
- English resource/help hub;
- Spanish resource/help hub;
- future stable category-specific resource paths.

Prefer long-lived semantic destinations over disposable campaign microsites. New category paths should use stable need/category concepts rather than organization names or campaign-recipient identifiers.

## Verification

Representative generated URLs should be tested for both English and Spanish pages. Verify that:

1. the intended page loads;
2. no redirect loop occurs;
3. GA4 can receive normal campaign attribution;
4. canonical/hreflang behavior remains clean;
5. internal navigation does not propagate campaign query parameters;
6. `scripts/analytics.js` semantic events continue to pass tests;
7. no private identifier appears in HTML, JavaScript, config, fixtures, logs, Issues, or PRs.

Do not generate fake production conversion clicks solely to create analytics evidence. Use repository/static tests and then wait for natural traffic.

## Interpretation boundary

Campaign analytics may support aggregate statements such as `cmp-02 generated sessions and book-view events`. It cannot support `Organization X clicked` or `Contact Y visited`.

`outbound_purchase` means a retailer-intent click, not a confirmed sale. Website engagement is not a confirmed library placement, review, backlink, or other durable publishing asset.
