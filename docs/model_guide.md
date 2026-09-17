# Solar-to-SAF model guide

An audited cost model for the Arizona 100,000-tonne/year solar-to-SAF project, updated **September 16, 2026**. It solves all **8,784 hours of the supplied 2024 weather year** with SciPy's bundled HiGHS solver. Gurobi is not required.

Start with the [full-year result](../results/2026-09-16/current_base/scenario_report.md), [scenario comparison](../results/2026-09-16/scenario_comparison.csv), [equations](model_equations.md), and [audit](model_audit.md). A [shareable PDF report](../results/2026-09-16/solar_saf_final_report.pdf) accompanies the completed analysis.

The base modeled cost is **$11.76/kg SAF**, or **$35.60/US gallon** at 0.8 kg/L. This is a conditional screening break-even estimate, not an observed SAF sale price. Source links and input statuses are in [model_assumptions.json](../config/model_assumptions.json) and [market_prices.json](../config/market_prices.json).

## Run

From the repository root after cloning or opening the project:

```bash
.venv/bin/python -m solar_saf.run_analysis
```

Default inputs resolve from the project location. Each run writes a new timestamped directory under `results/`, containing input snapshots, prices, solver status, versions, input/code hashes, costs, capacities, coproduct sales, hourly dispatch, scenario reports, and PNG/PDF figures. Explicit `--config`, `--prices`, `--solar`, and `--output` arguments accept paths relative to your working directory or absolute paths.

Sensitivity cases and regression checks:

```bash
.venv/bin/python -m solar_saf.run_analysis --sensitivity
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Cases include ±20% installed capital, half/double DAC capital, a 100 kt/year oxygen offtake allowance, no coproduct sales, and the legacy FT heat-unit interpretation. Cost/heat cases are reoptimized; sales-only cases use the mathematically identical optimal dispatch. These are not statistical confidence intervals. Each full solved case takes several minutes on this machine.

Regenerate figures and the PDF from a completed run:

```bash
.venv/bin/python -m solar_saf.plot_results results/2026-09-16
.venv/bin/python -m solar_saf.build_report results/2026-09-16
```

For a short test:

```bash
.venv/bin/python -m solar_saf.run_analysis --hours 168 --no-plots
```

**Short tests are not full-year cost/feasibility results.** Short mode extrapolates to 8,760 hours; full mode uses the actual calendar year with no extrapolation.

On another machine, create a Python 3.13 environment from the project root:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use the environment Python with `-m pip` so dependencies install into the environment used to run the model.

## Prices and updates

The checked [EIA page](https://www.eia.gov/dnav/pet/PET_PRI_SPT_S1_D.htm) shows September 9, 2026 observations released September 10:

| Product | USD/US gallon | Use |
|---|---:|---|
| Gulf Coast jet | 4.341 | Fossil benchmark only |
| Gulf Coast ULSD | 4.832 | FT diesel proxy |
| Mont Belvieu propane | 0.833 | LPG proxy |

No September 16 trade is claimed. Mass conversions use explicit density assumptions. Naphtha, wax and oxygen are unverified legacy prices; base oxygen revenue is zero. The checked snapshot and source HTML are in `data/prices/`.

Refresh to a new snapshot on a machine with internet access:

```bash
.venv/bin/python -m solar_saf.update_prices --as-of 2026-09-16 --output data/prices/eia_spot_prices_new.json
```

For a later analysis date, copy `config/model_assumptions.json` to a new configuration and set its `as_of` to the matching date. Pass that configuration with the new snapshot. For the date above:

```bash
.venv/bin/python -m solar_saf.run_analysis --config config/model_assumptions.json --prices data/prices/eia_spot_prices_new.json
```

The updater preserves source HTML and its hash, validates series/date columns, and rejects prices older than 14 days or releases after the analysis date. `--html path/to/page.html` supports offline parsing. Missing quotes are not invented; no EIA API key is needed.

## Project files

All paths below are relative to the project root.

| Path | Purpose |
|---|---|
| `solar_saf/optimization.py` | Optimization equations and feasibility checks |
| `solar_saf/solar_resource.py` | NSRDB weather parsing and solar generation |
| `solar_saf/run_analysis.py` | Model execution and scenario exports |
| `solar_saf/plot_results.py`, `solar_saf/build_report.py` | Figures and final PDF generation |
| `solar_saf/update_prices.py` | Fetch and validate updated price observations |
| `config/model_assumptions.json`, `config/capital_cost_sources.csv` | Engineering/economic inputs and source notes |
| `config/market_prices.json` | Default model price assumptions |
| `data/weather/arizona_nsrdb_2024_site_326317.csv.gz` | Required full-year Arizona weather input |
| `data/prices/eia_spot_prices_2026-09-16.json` and matching `.source.html` | Dated price snapshot and evidence |
| `tests/test_optimization.py`, `tests/test_market_prices.py` | Physical/economic and price-feed checks |
| `requirements.txt` | Python dependencies |
| `docs/` | This guide, equations, audit and file relocation record |
| `results/2026-09-16/` | Completed full-year scenarios, validation, figures and final report |

Each scenario contains `optimization_summary.json`, `model_assumptions_used.json`, `market_prices_used.json`, `optimized_capacities.csv`, `cost_breakdown.csv`, `coproduct_sales.csv`, `hourly_dispatch.csv`, and `scenario_report.md`. The run directory contains `run_manifest.json`, `scenario_comparison.csv`, `validation_summary.json`, `figures/`, and `solar_saf_final_report.pdf`.

All eight saved scenarios support the final report, including `legacy_ft_heat_kwh_basis`, a sensitivity case addressing an unresolved heat-unit assumption. Original run paths/hashes inside saved summaries remain historical provenance. [file_relocations.json](file_relocations.json) maps those paths to the current layout and records changes to support files. Weather is packaged losslessly as gzip; the reader accepts plain CSV and gzip. Numerical input values, optimization equations and saved calculation outputs are unchanged.

## Improvements and scope

- Correct UTC solar geometry, explicit DC/AC sizing, and counted twilight tracker stowing.
- Paid electrical heating, separate low/high temperature duties and installed heater capacity.
- Corrected stated DAC capital units and exposed uncertain equipment costs.
- Equipment-specific O&M, process contingency, compression, consumables and replacement allowances.
- Gas storage flow limits, battery duration limits, cyclic inventories and exact fuel target.
- Bounded coproduct sales, zero automatic carbon-removal credits and additive cost exports.
- Solver-independent feasibility checks and regression tests for physical conservation, dates and units.

The optimum is conditional on the linear model and its assumptions. Remaining gaps include supplier costs, reconciled Aspen heat/mass balances, multiple weather years, real offtake and plant availability. See the [audit](model_audit.md).

For differences between regression tests, short runs and the archived full-year analysis, see [Reproducibility](reproducibility.md). Upstream citations are collected in [References](references.md).
