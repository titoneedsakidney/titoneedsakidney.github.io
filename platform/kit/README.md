# Platform kit (generated; do not edit here)

This folder is copied into every repo by the platform repo's adopt_kit.py (in its tools folder) and kept current by a weekly timer. Edit the source in
`titoneedsakidney/automationpc-platform` (`kit/`), never here: the next sync overwrites it. `kit.json` lists every file with its sha256.

What it gives a worker in THIS repo, with no setup:

| Need | Use |
|---|---|
| Say why something failed or was refused, in a form a machine can read | `python3 platform/kit/reason.py CODE "detail"` (codes: `reason_codes.json`) |
| Track work in the common format | `platform/work-items.json` (format: `work-item.schema.json`), check with `python3 platform/kit/work_items.py check` |
| Pick the next item | `python3 platform/kit/work_items.py next` (this repo) or, from a platform checkout, `python3 tools/backlog.py next --portfolio` (every repo) |
| Give a builder job what it needs | optional item fields `allowed_paths`, `files_to_read`, `tests_to_run`, `rung_hint` (format: `work-item.schema.json`) |
| Know what a worker of a given kind may do | `python3 platform/kit/roles.py list` / `card ROLE` (shared cards in `roles.json`; product roles in roles.json inside this repo's platform folder, when it has one) |
| Record an incident as a replay case for the detector | `platform/incidents/INC-YYYY-MM-DD-slug.json` (format: `incident.schema.json`), check with `python3 platform/kit/incidents.py check` |
| Know what is a boundary | `python3 platform/kit/boundary.py list` (the list is `boundaries.json`; add repo rules in boundaries.json inside this repo's platform folder) |
| Prove no workflow would bill GitHub-hosted minutes | `python3 platform/kit/no_hosted_runners.py .` (the table-rules workflow runs it on every pull request) |
| Claim an item so nobody else takes it | `python3 platform/kit/claim.py claim ITEM --worker NAME` (tag lease; connector workers create the branch `claims/ITEM`) |
| Keep Tito's repeated corrections from recurring in an interactive Claude Code session | `.claude/settings.json` registers three hooks from this folder: `hook_session_start.py` (puts the platform's first steps, newest decisions and your next item in front of the session, also after a compaction), `hook_pre_tool_guard.py` (refuses HA merges 22:00-07:00, unrequested subagent spawns, `pkill -f`) `hook_fact_capture.py` (when Tito states a fact or corrects a repeat, tells the session to record it in docs/standing-facts.json at once) and `hook_stop_wording_lint.py` (warn-only wording log; `python3 platform/kit/hook_stop_wording_lint.py report`). They fail open; headless workers do not run hooks. |

**The rules every worker follows are one page: `WORKER_RULES.md` in this folder.** Every PR body ends with `item: <id>`; CI checks it (`check_pr.py`, workflow `.github/workflows/platform-kit.yml`, also generated). A product lead starts from `LEAD_BRIEF_TEMPLATE.md`. Background and decisions: START_HERE.md in the platform repo's docs folder.

## Shipping

From a platform checkout: `tools/ship_pr.sh <this-repo-worktree> "title" <item-id> "what and why"` commits, pushes, opens the PR with the `item:` line, waits for checks and merges only when every check passes. The item id must exist in this repo's `platform/work-items.json` or the platform backlog. Deploy by default: a merged green change deploys by itself; nothing waits for the owner except the approval class in destructive-actions.json in the platform repo's governance folder.
