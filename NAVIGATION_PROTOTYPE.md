# Navigation Prototype C: Unified Resources

Evaluation only. Do not merge or deploy this branch as-is.

Base production commit: `29eb66498cc8793e569be047436e363d6be3a9f0`

Primary navigation:

- Home
- My Story
- Resources
- Book

Spanish: Inicio, Mi historia, Recursos, Libro.

This option has the quietest primary menu. Resources opens one landing page that
separates kidney-care learning from organizations and practical help. Find Help
is therefore one level deeper. The organization entries on the Find Help pages
are clearly marked examples; they are not approved directory content.

## Test locally

```bash
git fetch origin
git switch --track origin/prototype/nav-c-resources-v2
python3 -m http.server 8000
```

Open `http://localhost:8000/`. Stop the server with Ctrl+C and return with
`git switch main`.

Try the same tasks in English, Spanish, and a narrow phone-sized window:

1. From Home, find the transplant nephrologist page.
2. From that page, find another transplant-team role.
3. Move from transplant information to dialysis information.
4. From the dialysis social-worker page, find online support-group help.
5. Pretend you do not know which organization you need and locate a sensible starting point.

Record where you hesitated as well as the click count. The branch changes the
top-level navigation and help-directory concept; it does not yet redesign every
deep clinical submenu.

+## Journey results

| Task | Clicks | What remains visible |
|---|---:|---|
| Home → pre-op transplant nephrologist | 3 | The transplant landing offers before-, during-, and after-surgery team routes |
| Nephrologist → another role in the same phase | 1 | The full phase-specific staff subnavigation stays visible |
| Transplant nephrologist → dialysis information | 1 | A contextual related link avoids backtracking |
| Dialysis social worker → online support groups | 1 to listing; 2 to a resource | Support groups, practical help, and all staff roles are suggested together |
| Starting dialysis → expectations and staff | 1 to expectations; 2 to staff | Dialysis subnavigation remains available |
| Caregiver → support and kidney education | 1 to support; 2 to education | Related dialysis and transplant guides are offered |
| No pathway fits → browse all topics | 1 | The primary learning destination remains visible |
| Spanish equivalents | Same | All tested internal routes remain under `/es/` |

The same cards and contextual links appear in all three options so the header
architecture—not a different set of content—drives the comparison.

From any deep page, Resources is one primary-navigation click away; Find Help
is a second click inside Resources. The four-item header is the calmest, but the
Resources label asks visitors to choose between learning and assistance after arrival.
