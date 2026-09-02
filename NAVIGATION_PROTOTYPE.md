# Navigation Prototype A: Guided

Evaluation only. Do not merge or deploy this branch as-is.

Base production commit: `29eb66498cc8793e569be047436e363d6be3a9f0`

Primary navigation:

- Home
- My Story
- Kidney Guide
- Find Help
- Book

Spanish: Inicio, Mi historia, Guía renal, Encontrar ayuda, Libro.

This option uses plain, task-oriented labels and gives Find Help a permanent
top-level location. The organization entries on the Find Help pages are clearly
marked examples; they are not approved directory content.

## Test locally

```bash
git fetch origin
git switch --track origin/prototype/nav-a-guided-v2
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
