# Final solar-to-SAF model

As of 2026-09-16. Scenario: capital_high_20pct.

**Modeled break-even production cost: $13.92/kg SAF** ($11.14/L; $42.17/US gallon at assumed 0.8 kg/L).

Annual SAF: 100.0 kt; net annual cost: $1,392.4 million; installed capital: $11.58 billion.

Gross cost before coproducts/support: $14.49/kg. Net coproduct revenue: $56.1 million/year.

Conventional jet benchmark: $1.43/kg, observed 2026-09-09. Premium: $12.49/kg. This is a fossil-fuel spot benchmark, not a SAF market quote or a long-term price forecast.

Optimization: optimal; 8,784 hourly intervals; 223.5 seconds. Independent balance checks passed.

Run scope: **FULL HISTORICAL CALENDAR YEAR**. Solar output: 22.11% of DC nameplate, or 29.63% of AC nameplate.

## Optimal capacities

| Component | Capacity | Unit |
|---|---:|---|
| solar | 3,720,437.1 | kWdc |
| electrolyzer | 1,158,503.0 | kW |
| dac | 96,852.4 | kg_co2_per_hour |
| rwgs | 51,163.7 | kg_co_per_hour |
| ft | 24,363.7 | kg_syncrude_per_hour |
| upgrading | 15,105.5 | kg_saf_per_hour |
| h2_storage | 123,422.4 | kg_h2 |
| co2_storage | 110,457.8 | kg_co2 |
| battery_power | 617,594.0 | kW |
| battery_energy | 3,939,955.9 | kWh |
| heater | 252,204.6 | kWth |

## Interpretation

Screening optimum for the stated linear-cost technology model, fixed production, and one historical weather year. Capital estimates use dated benchmarks escalated at an assumed 3% annually. Process equipment, DAC, storage, some duties, and unquoted coproducts remain engineering assumptions. Oxygen sales and policy credits are zero in the base case. FT heat supplies low-temperature DAC demand only; all auxiliary heat draws electricity and has installed heater capacity. Future forecasts, plant outage scheduling, full process simulation, tax financing, and a verified lifecycle analysis are outside this model.

## Price/source notes

- jet: latest verified observation is 2026-09-09 (7 days before as-of date).
- diesel: latest verified observation is 2026-09-09 (7 days before as-of date).
- lpg: latest verified observation is 2026-09-09 (7 days before as-of date).
- naphtha: unverified legacy price assumption; no current quote.
- wax: unverified legacy price assumption; no current quote.
- oxygen: unverified legacy price assumption; no current quote.

Full inputs, source links, version information and SHA-256 hashes are in `model_assumptions_used.json`, `market_prices_used.json`, and `optimization_summary.json`. Hourly quantities are in `hourly_dispatch.csv`; the cost breakdown has no subtotal rows that could double-count credits.

Original run paths and hashes describe the files at solve time. The [file relocation record](../../../docs/file_relocations.json) maps them to their current project locations.
