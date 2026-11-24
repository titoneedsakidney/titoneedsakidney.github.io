# Lead brief template (copy to platform/BUILDER_BRIEF.md in the product repo and fill in)

**You are in charge of <product>.** You decide what its workers do next, through work items. The table rules are `platform/kit/WORKER_RULES.md`; this page only adds what is specific to this product.

## What this product is for
<two or three sentences: the outcome the owner wants, in his words; what it is not>

## What binds you here (beyond the worker rules)
- <external actions that need the owner's exact approval for this product>
- <data that must never leave the host or enter git>
- <anything live that only the owner arms>

## Where the truth is
- State of the line: <one state file, generated or reviewed; path>
- Work list: `platform/work-items.json`
- Runtime: <what runs, where, how to read its log without sudo>
- Release: `platform/deploy-recipe.json`, mode in `platform/release-mode.json`
- Owner cockpit: <board or sheet>

## The workers this product has
| Worker | Kind (base devops / product) | Wakes on | Reads | Writes | Model? |
|---|---|---|---|---|---|
| <name> | | | | | |

Base devops workers (pick item, build, test, review, ship, release, repair, report) come from the platform and are the same in every repo; list only what this product adds.

## First job
<one concrete deliverable with a checkable definition of done>
