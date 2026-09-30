# Hosted GitHub Pages CD

The website is public and should stay off persistent home/self-hosted runners. Its acceptable CD boundary is GitHub-hosted validation plus GitHub Pages deployment.

## Release flow

```text
push to main
  -> Validate site (GitHub-hosted)
  -> successful workflow_run only
  -> re-check exact accepted SHA
  -> build deployable-only _site artifact
  -> GitHub Pages deployment environment
  -> public site
```

`workflow_dispatch` is retained for a manual canary, but it refuses any ref other than `main`.

The deploy workflow checks out the exact SHA that passed `Validate site`, reruns the release validation on that SHA, builds `_site`, uploads one immutable Pages artifact, and deploys it through the first-party Pages actions. It has no self-hosted runner, SSH key, server password, or home-network dependency.

## Artifact boundary

`scripts/build_pages_artifact.py` includes:

- deployable HTML pages outside repository-only directories;
- `assets/`;
- `data/`;
- `CNAME`, `robots.txt`, and `sitemap.xml` when present.

It excludes repository machinery such as `.github`, `docs`, `scripts`, `tests`, source includes, and pages marked `noindex`. The build refuses an artifact without `index.html` or `CNAME`.

## Permissions

Workflow default permission is `contents: read`.

Only the final `deploy` job receives:

- `pages: write`;
- `id-token: write`.

No repository-content write permission is used for deployment.

## Activation boundary

Merging the source is not enough to change the live site if the repository is still configured for branch-based Pages publishing. Activation is an explicit repository-setting action:

1. review/merge the CD source after `Validate site` passes;
2. in **Settings -> Pages**, set **Build and deployment / Source** to **GitHub Actions**;
3. manually dispatch `Deploy GitHub Pages` from `main` once;
4. confirm the deployment environment reports success;
5. verify the custom domain still resolves and HTTPS remains healthy;
6. verify several English/Spanish canonical pages plus `sitemap.xml` and `robots.txt`;
7. leave subsequent deployment driven by successful `Validate site` runs on `main`.

If the canary fails, switch Pages Source back to the previous branch configuration. No automationPC change or runner is involved.

## Explicit non-goals

- no persistent self-hosted runner;
- no deployment from pull requests;
- no arbitrary destination/server;
- no FTP/SFTP/SSH credentials;
- no website deployment capability in Research or automationPC Platform;
- no bypass of the existing site-integrity checks.
