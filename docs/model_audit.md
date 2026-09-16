# Review of the original project

Reviewed September 16, 2026. The original folder contained **182 project files**, excluding the virtual environment. Source/document text was read; CSV files were parsed, image files checked, and text was extracted from 56 PDFs/presentations. Image-only figures have no extractable text and are not independent evidence for the equations. Installed packages, macOS metadata and LaTeX build artifacts are not scientific inputs.

This audit preserves the findings after cleanup of superseded models, original papers/slides, duplicate data, and review working files. Paths such as `paper_latex.tex` or `Model_3_Byproducts/assumptions_used.json` in source metadata identify historical origins; those files are no longer included or needed at runtime. The inherited values and source limitations remain in [model_assumptions.json](../config/model_assumptions.json) and [capital_cost_sources.csv](../config/capital_cost_sources.csv).

The final project now groups code in `solar_saf/`, inputs in `config/` and `data/`, documentation in `docs/`, tests in `tests/`, and outputs in `results/`. [file_relocations.json](file_relocations.json) records previous/current paths and SHA-256 hashes. The optimization equations, solar calculations, input values, and completed numerical outputs are unchanged. Runner imports, default paths, export filenames and report references were updated. GitHub packaging adds gzip weather support; the decompressed input is byte-for-byte identical to the original CSV. Historical absolute paths and hashes inside saved optimization summaries describe the original solve and are preserved as provenance; use the relocation record to find current files. The archived run was not reoptimized during this reorganization.

## Findings that change the calculation

| Finding | Evidence in original project | Final treatment |
|---|---|---|
| Solar timestamps localized incorrectly | Every optimizer prefers `Local Time Zone=-7`, but the CSV specifies `Time Zone=0`. GHI peaks near 19–20 UTC. Saved dispatch has mean CF 0.052849. | Use UTC and verify zenith against NSRDB geometry. With explicit losses and DC/AC sizing, mean output is 0.221149 kW AC/kW DC, equivalent to 29.63% of AC nameplate. |
| Free auxiliary heat | Models 2–4 use `Q_aux_heat` without linking it to energy consumption or cost. Model 3 exports about 1.208 billion kWh of this heat over the weather year. | Every auxiliary thermal kW draws electricity through a 98% efficient heater. Heater capacity is optimized and purchased. |
| Heat temperature grades ignored | Old balance allows FT heat to serve RWGS, although diagrams put FT around 220°C and RWGS around 850°C. | FT heat serves DAC only. RWGS and upgrading use electric heat. |
| Thermal units disagree | Documentation calls FT heat 4.3 MJ/kg, code calls it 4.3 kWh/kg. DAC/RWGS also have contradictory MJ/kWh labels. | Base uses 4.3 MJ/kg FT and 1.2 MJ/kg upgrading (divide by 3.6); DAC 2 and RWGS 1.5 kWh/kg follow the executable. Legacy FT kWh is a sensitivity case, not validated performance. |
| DAC capital conversion wrong | Code/reference PDF equate 1,100 USD/(tCO2/year) to 126 USD/(kg/hour). | 1,100 × 8,760 / 1,000 = **9,636 USD/(kg/hour)**. This corrects the stated basis without independently verifying the 1,100 benchmark. Half/double DAC cases expose uncertainty. |
| Model 4 saved results copied | Model 3/4 README, assumptions, cost breakdown, dispatch, history and summary files have identical hashes. Carbon credit is absent from Model 4 saved assumptions. | Do not present its $12.26/kg as a solved carbon-credit scenario. Generate a new result manifest. |
| Automatic removal credit | Model 4 credits DAC output at 180 USD/t without eligibility, displacement factor, duration or lifecycle analysis. | Base policy support is zero. CO2 converted to fuel is utilization; permanent removal is not demonstrated. Any supplied support must already be verified and levelized. See [IRS instructions](https://www.irs.gov/instructions/i8933). |
| Guaranteed oxygen sales | Model 3 sells all approximately 567 kt/year oxygen without buyer demand or conditioning costs. | Zero oxygen revenue in base. Optional sales have an annual cap, sale fraction and conditioning allowance. |
| Duplicate credit subtotal | Model 3 exports individual revenue rows and `TOTAL BY-PRODUCT CREDIT`; summing all rows counts credits twice. | Final cost breakdown has additive line items only and reconciles to the objective. |
| Manuscript/executable disagree | `paper_latex.tex` gives different electricity, H2, cost and yield values from its figures/scripts. No Aspen simulation files are present. | One input JSON is authoritative. Manuscript process CAPEX is an engineering assumption. No claim of newly validated Aspen performance. |
| Leap-year mismatch | 8,784 observations, although papers say 8,760. Old models apply 8,760/8,784 scaling. | Full mode uses complete 2024 and exactly 100 million kg that year. Short tests are clearly labeled annual extrapolations. |
| Costs lack dated evidence | Generic references and incomplete technology costs in old files. | Use DOE installed PEM estimate and 2025 Q1 PV benchmark, with vintage and assumed escalation. R&D targets are not current supplier costs. |
| Some figures embed old results | Models 1/2 plotters embed results and obsolete Downloads paths. Model 4 plotter labels Model 3. Literature ranges have incomplete support. | Final plots read final exports. Superseded figures and papers were removed during cleanup. |

The timezone-only diagnostic, using the same legacy PVWatts parameters, changed mean capacity factor from **0.0528492097** to **0.2649782657**. This isolates the timestamp correction; the final profile also applies losses, inverter sizing and lifetime derating, giving the different value in the table above.

## Final model boundary

The final model is a deterministic **linear program** using linear installed costs for modular capacity. It does not retain the original concave piecewise cost curves and unverified reference sizes; its global LP optimum is conditional on this changed cost formulation. It co-optimizes PV, electrolysis, DAC, synthesis, upgrading, batteries, gas storage and heaters over the full weather chronology.

H2/CO2 inventories are cyclic and lossless, with finite charge/discharge rates. Battery losses, throughput charges and duration limits are explicit; exported solutions are checked for simultaneous charging/discharging. SAF production remains at least 25% of capacity and ramps at most 10%/hour, including the year boundary. This is continuous operation with turndown, not a startup/unit-commitment model.

The fixed SAF equality and fixed yields fix coproduct quantities. Oxygen/no-sales scenarios can therefore reuse the optimal design exactly; cost/heat scenarios require reoptimization. The LP objective is gross annual cost. Subtracting constant revenue leaves the minimizer unchanged and gives net LCOF. There is no excess-production incentive.

Costs use a stated 2024 monetary basis and **3%/year assumed escalation** to 2026, followed by constant real cash flows and an 8% real discount rate. This is not measured inflation or a quote. Replacements use an equivalent-full-load stack reserve and a discounted battery allowance. No end-of-project residual value is credited. PV lifetime derating is a screening approximation.

EIA diesel/propane observations are proxies for FT coproduct prices. Naphtha, wax, oxygen, storage and several process inputs remain unverified. Exclusions include detailed process simulation, startup/outage behavior, water recovery, full carbon lifecycle, grid imports, electricity exports, tax depreciation, financing during construction, distribution and certified SAF premiums. The model does not establish ASTM compliance or forecast a 25-year commodity-price path.

The new result is internally consistent and reproducible, but neither the legacy $12.26/kg nor the new base cost is a validated vendor-level budget. Their difference is not an isolated technological improvement.
