# Analytics measurement hygiene

The website uses GA4 measurement ID `G-JHT0DBJBHH` for aggregate page and
purpose-event reporting. The identifier is public configuration, not a secret.
Private aggregate exports and Search Console query data remain outside this
repository.

## Measurement map

| Surface | Behavior | Data boundary |
|---|---|---|
| Every standalone HTML page | Queues the standard GA4 configuration and default `page_view` | The production-only loader decides whether the Google tag may load |
| `scripts/analytics-loader.js` | Loads Google Analytics only on `https://titoneedsakidney.com` | Localhost, IP previews, copied hosts, and explicit audit sessions are suppressed |
| `scripts/analytics.js` | Emits `cta_click` and approved purpose events from stable link metadata | No visible link text, destination URL, visitor identifier, or form value |
| Private Research workflow | Reads aggregate GA4 and Search Console reports weekly | No write access to Analytics and no visitor-level export |

Calling `gtag('config', ...)` sends a `page_view` by default once the Google tag
loads. Google documents both that default and the `ga-disable-MEASUREMENT_ID`
switch used by the loader:

- <https://developers.google.com/analytics/devguides/collection/ga4/reference/config#send_page_view>
- <https://developers.google.com/tag-platform/security/guides/privacy#turn_off_google_analytics>

## Test-traffic paths

| Traffic source | Before the hostname gate | Repository control |
|---|---|---|
| Owner browsing the live site | Indistinguishable from other production visits | Use GA4 internal-traffic labeling in Testing mode; use audit mode for deliberate checks |
| Local HTTP preview (`localhost` or `127.0.0.1`) | Could load the production tag and send pages/events | Suppressed by the canonical-origin allowlist |
| Local `file:` preview or a copied/preview hostname | Could load the production tag where the browser allowed it | Suppressed by the canonical-origin allowlist |
| Static Python checks, Node tests, GitHub Pages builds, or `curl` | Do not execute page JavaScript and do not send GA events | No additional suppression needed |
| JavaScript-capable browser, Lighthouse, or WebDriver audit of production | Can send ordinary production traffic | Start the tab with `?analytics_test=1` |
| Link preview, safety scanner, or unrecognized automation | May execute JavaScript and may resemble a visit | Do not guess from user agent; retain hostname/source diagnostics |
| Browser privacy protection or an analytics blocker | Can prevent measurement and cause undercounting | Treat GA4 as directional, not a census |

GA4 automatically excludes known bots and spiders, but that does not establish
that every remaining event is a person. See
<https://support.google.com/analytics/answer/9888366>.

GA4's Developer Traffic filter applies only to events sent with debug mode
enabled. This site does not enable debug mode for ordinary audits, so that
filter is not a substitute for the repository gate:
<https://support.google.com/analytics/answer/13296662>.

## Deliberate production audits

Open the first audit page with the test flag:

```text
https://titoneedsakidney.com/?analytics_test=1
```

That page and later same-origin navigation in the same tab do not load the
Google tag. Close the tab to end the session-scoped audit mode. Do not use the
flag for ordinary outreach or visitor links.

## Baseline boundary

The aggregate snapshot through 2026-08-30 contains one `127.0.0.1` session,
two `ko-fi.com` hostname sessions, and a large unresolved direct-desktop segment.
It can support directional page and search-priority work, but not a precise claim
about audience size, campaign causality, or differences between navigation
alternatives.

The purpose-event schema first reached production on 2026-09-02. A clean
measurement-hygiene cutoff does not exist while this safeguard is unmerged and
the owner traffic rule is unverified. Record the first full reporting day after
both conditions are true as the clean-baseline start; do not rewrite the older
history.

Google's internal-traffic filter permanently discards matching data only in
Active mode. Keep it in Testing until its labels have been checked in Explore:
<https://support.google.com/analytics/answer/10104470>.

## One-time GA4 owner checklist

1. In GA4 property `372315173`, open **Admin → Data streams → the website stream
   → Configure tag settings → Show more → Define internal traffic**. Open or
   create `Tito owner traffic`, keep `traffic_type` as `internal`, and add the
   public IP address or addresses used for owner testing. Save; do not put those
   addresses in GitHub.
2. Open **Admin → Data collection and modification → Data filters → Internal
   Traffic**. Set the filter to **Exclude**, parameter value `internal`, state
   **Testing**, and save. Do not select Active.
3. Visit one production page normally. After 24–36 hours, use **Explore → Free
   form** with rows `Test data filter name` and `Event name`, value `Event count`,
   and confirm the internal filter label appears on `page_view`. Leave the filter
   in Testing and report only `internal traffic visible in testing`.
