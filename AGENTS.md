# Agent Rules — Autonomous, Low-Friction Delivery

## Purpose

This repository is operated by a small human-and-AI team. The goal is useful working software and evidence, not change-control theatre.

## Default mode

- Own a bounded issue from investigation through tested implementation, review, merge, deployment, and outcome reporting when the task is reversible and covered by the repository's release lane.
- Infer routine engineering choices from the issue, existing code, tests, and stated product intent. Do not pause for confirmation on ordinary implementation details.
- Keep going through research, coding, test repair, documentation, CI repair, and small follow-on fixes until there is a real blocker or a working result.
- Prefer the smallest end-to-end change that can be used and evaluated. A simple working version beats a speculative framework.
- Use one branch and one PR per coherent task. Do not create process-only Issues, duplicate checkpoints, or a chain of handoffs for a single outcome.

## Canonical website work list

The website repository's single machine-readable queue is `platform/work-items.json`. Use the platform kit's `platform/kit/work_items.py next` and `platform/kit/claim.py` after the platform kit is adopted; the platform's `tools/backlog.py next --portfolio` is the unified cross-repo view. Every code PR must identify the exact website work item ID. Before the kit is synced, work directly from the canonical JSON on main rather than inventing another task list or an untracked claim.

GitHub Issue #17 is the evidence, scope, discussion and content review record for the kidney directory, **not a parallel task queue**. Research's `resource-page-live` represents the Book Factory's external-promise outcome, **not a second website implementation list**. Split or revise work only in this file using the platform `expand-vague-items` playbook: one test command, bounded paths, source facts, explicit dependencies and headless boundaries.

## Review and deployment

Normal path for routine, reversible work:

1. agent implements and runs relevant checks;
2. an AI review checks scope, diff, tests, and rollback;
3. merge and deploy through the fixed project release lane;
4. Tito uses the result and gives product feedback;
5. adjust or revert if it misses the mark.

A draft PR is for incomplete work or a genuine design decision—not a mandatory waiting room. Do not ask for a separate approval merely to proceed from tested code to a routine deployment.

Backup, validation, health checks, and rollback are release-lane internals. The operator should see one clear result: **deployed**, **refused before change**, or **rolled back**, with the reason and recovery point.

When a release lane is missing or awkward, build or repair one shared lane. Do not replace it with a growing collection of manual copy/paste packets or project-specific helpers.

## Stop only for a real boundary

Ask before:

- irreversible deletion, destructive migration, or data loss risk;
- spending money, sending public/external communications, or making a financial/account decision;
- creating, revealing, changing, or broadening credentials, permissions, or network exposure;
- changing live control behavior that can affect people, property, or equipment;
- an ambiguity that materially changes the user-visible outcome.

A failed normal deployment is not a crisis: capture the error, restore the known snapshot if needed, report it, and improve the lane.

## Reporting

GitHub is the durable record. Post only meaningful updates:

- a useful discovery;
- a ready PR or deployed result;
- a real blocker with the exact next authority/input needed;
- a rollback or lesson that changes the next attempt.

Do not turn routine progress into a stream of permission questions. Never make Tito relay outputs between agents when GitHub, the repository, or the approved host interface can carry the evidence.

## Repository boundary

Follow the repository's data/privacy rules and use its approved release interface. Do not expose secrets or private data in Git, logs, PRs, Issues, dashboards, or screenshots.

## Website boundary

Routine content, UX, analytics, SEO, and accessibility improvements may publish after repository checks and AI review. Preserve bilingual parity and run the documented static-site integrity checks. Do not publish new medical, legal, fundraising, or partner claims without source material or an explicit issue decision.

Campaign-attribution or outreach-landing work must also follow `docs/CAMPAIGN_ATTRIBUTION.md`. Accept controlled cohort UTMs, preserve clean canonical/hreflang/internal URLs, and never add recipient-, organization-, contact-, CRM-, or Gmail-level identifiers to public analytics or links.
