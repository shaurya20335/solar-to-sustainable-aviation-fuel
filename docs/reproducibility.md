# Reproducing and interpreting the reference analysis

The reference analysis is stored in `results/2026-09-16/`. Its course context is Fall 2025, its economic assessment date is September 16, 2026, its weather year is 2024, and its verified EIA observations are dated September 9, 2026.

## Three levels of verification

| Level | What it checks | What it does not establish |
|---|---|---|
| Regression tests | Conservation, units, prices, operating constraints and CSV/gzip parsing | Full-year economics or commercial performance |
| 168-hour smoke run | Input loading, model construction, solver and export integration | The saved full-year cost or annual feasibility |
| Full-year base/sensitivity run | Optimization over all 8,784 supplied hours under the stated assumptions | Independent process simulation, vendor costs or lifecycle certification |

Install the environment and run the checks using the [README](../README.md). GitHub Actions runs the first two levels. The [archived validation record](../results/2026-09-16/validation_summary.json) describes checks performed on the saved full-year scenarios; its historical test count is not a live count of the current test suite.

## Re-run the reference configuration

From a fresh clone, with dependencies installed:

```bash
.venv/bin/python -m solar_saf.run_analysis --sensitivity
```

Each execution creates a new timestamped result directory and leaves the reference directory intact. Cost and heat cases are reoptimized; the two sales-only cases reuse the base solution because revenue changes are constant under the fixed production/yield assumptions.

The reference base cost is **11.75681411347789 USD/kg SAF**, rounded to **11.76 USD/kg** in the report. Compare objective values, annual output, constraint residuals and assumptions before comparing individual hourly decisions. Floating-point arithmetic and alternative optimal dispatches can produce small differences across solver/library versions.

Original runs record Python 3.13.7, NumPy 2.3.5, pandas 2.3.3, SciPy 1.16.3 and pvlib 0.13.1. See [requirements.txt](../requirements.txt) for the current dependency specification. The certificate bundle has a minimum version rather than an exact pin; it supports price-source access and is not a process-model parameter. This repository does not promise byte-identical generated PDFs or figures across operating systems.

## Input identity and historical paths

The model reads `data/weather/arizona_nsrdb_2024_site_326317.csv.gz` directly. Its decompressed SHA-256 matches the original CSV used by the saved run; [weather provenance](../data/weather/README.md) records the value. Compression changes storage, not weather observations.

`input_code_sha256` and `solar.source_file` inside archived optimization summaries record the original solve-time filenames. They are historical metadata, not required local directories. [file_relocations.json](file_relocations.json) maps original filenames to current repository paths. For gzip weather, compare the decompressed checksum; for files changed during packaging, distinguish the original hash from the recorded current hash.

The numerical optimization equations, physical input values and saved full-year outputs were preserved during packaging. Reader/import/output-path changes are documented separately. Input JSON copies within each scenario are authoritative for that scenario.

## Reviewing a new result

Record the commit, input snapshots and observation dates. Inspect solver status and feasibility checks, reconcile cost totals, and retain the manifest and scenario comparison. Publish revised results in a new dated directory after review. Explain any scientific changes in the report; do not relabel the saved analysis as newly solved.

The [model guide](model_guide.md) documents price updates and report generation. The [references](references.md) identify upstream sources, and the [audit](model_audit.md) describes the remaining scientific limitations.
