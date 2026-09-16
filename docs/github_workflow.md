# Git and GitHub workflow

Repository: `shaurya20335/solar-to-sustainable-aviation-fuel`
Visibility: public
Default branch: `main`

## First publication

Install the [GitHub CLI](https://cli.github.com/) and sign in through its browser flow; keep tokens out of project files and commit messages:

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth status
```

From the prepared project root, confirm the commit and publish it as a new repository:

```bash
git status
git log -1 --oneline
gh repo create shaurya20335/solar-to-sustainable-aviation-fuel --public --source=. --remote=origin --push --description "NYU Tandon Fall 2025 course project: solar-to-SAF techno-economic optimization for CBE-GY 9413 A / CUSP-GX 9113 A."
```

Use `gh repo create` only for the first publication. If the repository already exists, inspect `git remote -v` and use `git push -u origin main` with the correct remote. Avoid initializing a separate README on GitHub when uploading this existing project.

## Make a focused change

Keep one logical change in each commit. Use a short branch name and stage explicit paths after inspecting the diff:

```bash
git switch main
git pull --ff-only
git switch -c docs/improve-model-guide
# Edit the guide, then inspect exactly what changed.
git diff -- docs/model_guide.md
git add docs/model_guide.md
git diff --cached
git diff --cached --check
git commit -m "docs: clarify model setup and assumptions"
git push -u origin docs/improve-model-guide
gh pr create --base main --title "Clarify model setup and assumptions" --body "Document setup steps and input assumptions. Validation: reviewed commands and relative links."
```

For code/input changes, run relevant checks before committing:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m solar_saf.run_analysis --hours 168 --no-plots
```

Before merging, inspect the changed files and GitHub Actions results. A method or input change needs an appropriate full analysis before new scientific results are presented as final. Preserve prior dated outputs; identify the input vintage of each new result directory.

## Commit messages

Use an imperative subject that describes the effect. These prefixes are a project convention:

| Prefix | Example |
|---|---|
| `feat:` | `feat: add a storage-cost sensitivity case` |
| `fix:` | `fix: reject missing hourly weather records` |
| `docs:` | `docs: explain coproduct price assumptions` |
| `test:` | `test: verify compressed weather equivalence` |
| `data:` | `data: add a dated EIA price snapshot` |
| `chore:` | `chore: update the Python dependency set` |

For a substantial change, add a body explaining the reason, result and validation. Avoid combining unrelated model changes, formatting and regenerated outputs in one unexplained commit. Use descriptive messages rather than `updates` or `final final`.

## Files and result review

Commit source, tests, documentation, reviewed input snapshots and intentional result artifacts. The `.gitignore` excludes `.venv`, caches, `.env` files, the optional uncompressed weather copy, and newly generated runs. To publish a reviewed run, explicitly add its directory to the ignore allowlist and include its inputs, manifest, solver checks and report.

The original 178,156,331-byte weather CSV exceeds GitHub's [100 MiB ordinary-file limit](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). This project versions an equivalent `.csv.gz` file and reads it directly. Adding an ignore rule after committing an oversized file does not remove it from earlier commits. The unpublished initial commit was prepared without that oversized blob; its previous version is retained locally at `refs/archive/pre-github-publication` and is not a branch to push.

Normal updates use ordinary commits and pushes. Do not force-push shared history for routine corrections; add a corrective commit or use a reviewed revert. No force-push is required for this project's initial publication.

GitHub references: [create a repository](https://cli.github.com/manual/gh_repo_create), [browser authentication](https://cli.github.com/manual/gh_auth_login), and [create a pull request](https://cli.github.com/manual/gh_pr_create).
