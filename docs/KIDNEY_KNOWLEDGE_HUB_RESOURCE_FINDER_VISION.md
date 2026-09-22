# Kidney Knowledge Hub — Resource Finder Vision

Status: Product direction for future discussion and implementation  
Recorded: 2026-09-22

## Core idea

Evolve the Kidney Knowledge Hub from a primarily hierarchical collection of topic pages into a user-centered resource-finding experience.

The current hierarchy remains valuable and should be preserved. The change is to add a clearer front door that starts with the visitor's situation or question rather than requiring them to understand the site's taxonomy first.

The guiding question is:

> **What are you trying to figure out?**

## Primary front-door choices

Start with roughly six large, plain-language situation cards:

- I was just diagnosed.
- I'm starting or living on dialysis.
- I'm preparing for a transplant.
- I'm waiting for a transplant.
- I'm recovering after transplant.
- I'm considering donating a kidney.

Each card should include a short explanation in plain language. The card text, not the icon, is the interface.

Also include a prominent:

- **I don't know where to start.**

This should be treated as a normal route, not a failure state.

## Secondary need-based shortcuts

Below the journey/situation cards, provide shortcuts for specific needs such as:

- Money & insurance
- Work & disability
- Transportation
- My care team
- Medications
- Food & nutrition
- Emotional support
- Helping someone else

These are alternate entry points into the same underlying content, not separate silos.

## Resource model

Treat "resource" broadly. A resource can be:

- an educational guide;
- a care-team explainer;
- a checklist;
- a patient or donor story;
- an external organization or assistance program;
- a book excerpt or lived-experience resource;
- eventually other useful tools.

The Hub should be able to surface different resource types together when they answer the same user need.

Example: a search for "lost wages" could eventually return a financial-coordinator explainer, a living-donation financial guide, a relevant assistance organization, and a lived-experience story.

## Flags / badges

Use restrained badges on resource results as secondary signals. Do not overload the initial choice cards with metadata.

Initial badge vocabulary:

- START HERE
- GUIDE
- STORY
- CHECKLIST
- CARE TEAM
- ORGANIZATION
- FREE
- NATIONWIDE
- ESPAÑOL

Show no more than roughly 2–3 visible badges per result. Additional attributes can remain in metadata and filters.

Do not use national flags to represent languages. Use EN / ES or English / Español.

Icons may reinforce meaning but must not replace clear text labels.

## Preserve conventional browsing

Do not remove the existing information architecture.

Below the new discovery interface, preserve a conventional "Browse the full Hub" section such as:

- Dialysis
- Transplant
- Living Donation
- Care Team
- Patient & Donor Stories
- All Resources

The existing hierarchy remains useful for SEO, power users, internal linking, and predictable navigation.

## Search and filtering direction

A future Hub can support search and filtering without requiring AI.

Resource metadata can include fields such as:

- journey
- stage
- needs
- audience
- type
- language
- geography
- start_here

Vanilla JavaScript can use this metadata to return relevant resources.

The public Organization Directory can later become one filtered view of this larger resource system rather than a separate conceptual silo.

## Architectural principle

Do not make visitors understand the site's taxonomy before they can get help.

The Hub should support both:

1. **Where am I?** — journey/stage-based discovery.
2. **What do I need?** — problem/need-based discovery.

Both routes should lead into the same underlying collection of resources.

## Current design direction

Preferred top-level experience:

1. Search bar.
2. "What are you trying to figure out?" situation cards.
3. "I need help with something specific" shortcuts.
4. Resource results with restrained badges.
5. Conventional browse hierarchy below.
6. Strong cross-linking between educational pages, stories, care-team pages, and eventually verified external organizations.

This is a recorded product vision, not an instruction to implement the redesign yet.
