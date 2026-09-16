# Final solar-to-SAF model

As of 2026-09-16. Scenario: dac_capital_double.

**Modeled break-even production cost: $13.32/kg SAF** ($10.65/L; $40.33/US gallon at assumed 0.8 kg/L).

Annual SAF: 100.0 kt; net annual cost: $1,331.7 million; installed capital: $10.83 billion.

Gross cost before coproducts/support: $13.88/kg. Net coproduct revenue: $56.1 million/year.

Conventional jet benchmark: $1.43/kg, observed 2026-09-09. Premium: $11.88/kg. This is a fossil-fuel spot benchmark, not a SAF market quote or a long-term price forecast.

Optimization: optimal; 8,784 hourly intervals; 393.3 seconds. Independent balance checks passed.

Run scope: **FULL HISTORICAL CALENDAR YEAR**. Solar output: 22.11% of DC nameplate, or 29.63% of AC nameplate.

## Optimal capacities

| Component | Capacity | Unit |
|---|---:|---|
| solar | 3,773,874.4 | kWdc |
| electrolyzer | 1,158,808.6 | kW |
| dac | 93,446.6 | kg_co2_per_hour |
| rwgs | 50,310.1 | kg_co_per_hour |
| ft | 23,957.2 | kg_syncrude_per_hour |
| upgrading | 14,853.5 | kg_saf_per_hour |
| h2_storage | 125,646.9 | kg_h2 |
| co2_storage | 198,223.0 | kg_co2 |
| battery_power | 649,610.4 | kW |
| battery_energy | 3,960,265.5 | kWh |
| heater | 244,417.1 | kWth |

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
