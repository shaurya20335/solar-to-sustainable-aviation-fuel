# Final model equations and units

The code in [solar_saf/optimization.py](../solar_saf/optimization.py) is a linear capacity-expansion and hourly-dispatch model. This document describes the final model implementation and supersedes inconsistent equations in historical manuscripts.

## Dimensions and chronology

Internally use MW (electricity), MWth (heat), MWh (battery inventory), tonnes (gas inventory), tonnes/hour (process rates), and million USD/year (objective). All time steps last one hour. The 2024 input contains 8,784 hours, indexed in UTC. The first interval's predecessor is the final interval, making the operation cyclic.

Inputs and exports label capital in the original units: USD/kW, USD/kWh, USD/kg, or USD/(kg/hour). Multiplying an internal capacity by 1,000 converts it to its reported base unit. At one tonne/hour, a specific requirement of one kWh/kg is one MW.

Solar capacity is MW **DC**; the resource profile is AC MW per DC MW. Thus `P_solar[t] = CF[t] × C_PV`. Inverter AC nameplate is `C_PV / dc_ac_ratio`. There is no grid import or electricity export.

## Process surrogates

Let `s[t]`, `h[t]`, and `d[t]` be SAF, hydrogen-production, and DAC-capture rates. Let `y=0.62` be the SAF yield from syncrude. Then:

```text
syncrude[t] = s[t] / y
CO[t]       = (2.1 / y) s[t]
H2_use[t]   = [(2.1/y)(2/28) + (0.28/y) + 0.02] s[t]
CO2_use[t]  = [(2.1/y)(1/0.52)] s[t]
```

These are aggregate process coefficients. The factor 0.52 is a CO/CO2 **mass-yield assumption**, not a 52% molar single-pass conversion. Recycle loops, by-gas composition, water recovery, and a complete elemental/process-simulation balance are not represented. The project contains no Aspen source files with which to independently validate those coefficients.

The four hydrocarbon coproduct rates are their mass fractions (0.18/0.13/0.05/0.02) times syncrude rate. Their fractions plus SAF sum to one. Electrolytic oxygen is eight times hydrogen production by mass.

## Conservation

For each hour and cyclic predecessor `prev`:

```text
H2_stock[t]  - H2_stock[prev]  = h[t] - H2_use[t]
CO2_stock[t] - CO2_stock[prev] = d[t] - CO2_use[t]
B_stock[t]   - B_stock[prev]   = sqrt(0.85) B_charge[t]
                                 - B_discharge[t] / sqrt(0.85)

P_solar[t] + B_discharge[t] = P_electrolyzer[t] + P_compression[t]
                           + P_DAC_electric[t] + P_synthesis[t]
                           + P_heater[t] + B_charge[t] + P_curtail[t]
```

All flows and capacities are nonnegative. Gas inventories are lossless as assumed, and their hourly net flows are bounded by 25% of storage capacity. Gas storage is not a source of annual hydrogen or carbon.

Electrical loads include 55 kWh/kg H2 for electrolysis, 3 kWh/kg H2 compression, 0.4 kWh/kg CO2 capture, 0.1 kWh/kg CO2 compression, plus synthesis-unit coefficients. The number 1.23 kWh/kg syncrude is an **electricity requirement**, not an efficiency greater than one or an electricity-production term.

## Heat

Low-temperature DAC heat demand is `2 d[t]` MWth. Recoverable FT heat is `(4.3/3.6) × 0.8 × syncrude[t]` MWth. A nonnegative purchased electric-heat duty `q[t]` closes the deficit:

```text
2 d[t] <= (4.3/3.6) × 0.8 × syncrude[t] + q[t]

high_grade_heat[t] = 1.5 CO[t] + (1.2/3.6) s[t]
P_heater[t]        = (q[t] + high_grade_heat[t]) / 0.98
q[t] + high_grade_heat[t] <= C_heater
```

FT heat cannot serve the high-temperature requirement. Unused FT heat is rejected. Thermal duties remain screening assumptions with the documented legacy unit conflict; no detailed heat-exchanger network is implied.

## Capacity and operating envelopes

Electrolyzer electrical load, DAC rate, CO rate, syncrude rate, SAF rate and each stock have corresponding purchased-capacity bounds. Battery charge **plus** discharge is limited by converter capacity; its energy/power duration is between two and eight hours.

```text
0.25 C_upgrading <= s[t] <= C_upgrading
abs(s[t] - s[prev]) <= 0.10 C_upgrading
sum(s[t]) = 100,000 tonnes       # full-year mode
```

Ramping includes the year boundary. There are no startup/shutdown binaries or scheduled outages. Battery complementarity is not a binary constraint; losses, curtailment and positive throughput cost make simultaneous cycling unnecessary, and the exported solution is explicitly checked to exclude it within numerical tolerance.

## Economics

Capacities have linear installed costs. No additional economies of scale are inferred from arbitrary reference sizes. The selected coefficients, including their statuses and sources, are recorded in [model_assumptions.json](../config/model_assumptions.json) and [capital_cost_sources.csv](../config/capital_cost_sources.csv).

```text
CRF = r / [1 - (1+r)^(-n)]        # 1/n when r=0
gross annual cost = annualized installed capital + component O&M
                  + replacement allowances + water + catalyst + DAC sorbent
                  + battery throughput cost
net annual cost   = gross cost - coproduct sales + oxygen conditioning
                  - externally specified annual-equivalent policy support
LCOF              = net annual cost / fixed annual SAF kilograms
```

The default project has `r=8%` real and `n=25` years. Historical dollar benchmarks are escalated to the analysis year at an assumed 3% annually, then held constant in real terms. DAC/RWGS/FT/upgrading/heater installation includes a 20% contingency. Stack replacement is a usage-based reserve using 450 USD/kW and 40,000 equivalent full-load hours. Battery energy equipment has a 60% replacement allowance at year 15, discounted and annualized across the project. These simplifications are explicit assumptions, not measured degradation models.

Coproduct revenue is constant with respect to design/dispatch: the exact SAF target fixes syncrude and coproduct masses, while cyclic gas inventories fix total hydrogen and oxygen production. Hence the solver minimizes gross cost and reporting subtracts constant revenue. Oxygen sales are bounded by produced volume, a sale fraction, and an annual offtake cap. Zero is the default. No automatic carbon-removal credit applies.

## Certification and limitations

HiGHS must return an optimal status. A second calculation checks every exported solution against the sparse equality/inequality matrices, bounds and battery cycling, and the financial export must sum to the solver-derived net total. Regression tests also calculate physical balances directly from output columns, test cyclic feedstock conservation, exercise price dates/units, and verify the effect of removing heat or increasing costs.

An optimal mathematical solution is not a prediction of commercial project performance. It assumes perfect knowledge of one historical weather year, fixed process coefficients, constant real product prices, continuous operating capability and the specified linear costs. Vendor estimates, multi-year weather/availability analysis and an independently reconciled process simulation remain necessary for a project-grade estimate.
