# Contributing

This repository contains a course project and a dated reference analysis. Contributions should keep the scientific assumptions, implementation and reported results consistent.

## Report an issue

Use [GitHub Issues](https://github.com/shaurya20335/solar-to-sustainable-aviation-fuel/issues). Include the commit, Python/dependency versions, command, relevant configuration, and expected versus observed behavior. For a numerical concern, identify the equation, unit, source or scenario involved and provide a small reproducible example where possible.

## Propose a change

Use a focused branch and pull request. Describe the problem, resulting behavior, affected assumptions and validation. Cite primary sources for new parameters; distinguish observed values from estimates. Keep numerical changes separate from unrelated formatting or documentation edits.

Run relevant checks from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m solar_saf.run_analysis --hours 168 --no-plots
```

A short run checks software behavior; it does not validate a replacement full-year result. Changes to model equations or input values require an appropriate full analysis before publishing revised scientific conclusions.

Preserve the reference analysis in `results/2026-09-16/`. New reviewed results should have their own directory, input snapshots, manifest and validation evidence. Update documentation with any command or filename change.

See the [Git workflow](docs/github_workflow.md) for branch, commit and pull-request examples, and the [reproducibility guide](docs/reproducibility.md) for validation levels.

Original project code and documentation are MIT licensed. Third-party datasets, source snapshots and dependencies retain their own terms; see the [source attribution](docs/references.md).
