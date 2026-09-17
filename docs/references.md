# References and source attribution

These references identify the software, datasets and benchmarks used by the project. They are not a systematic literature review or independent validation of the complete process model. Parameter-specific values, dates and source statuses are recorded in [model_assumptions.json](../config/model_assumptions.json) and [capital_cost_sources.csv](../config/capital_cost_sources.csv).

## Scientific software

1. Holmgren, W. F., Hansen, C. W., and Mikofski, M. A. (2018). [pvlib python](https://joss.theoj.org/papers/10.21105/joss.00884). *Journal of Open Source Software*, 3(29), 884. DOI: 10.21105/joss.00884. Used for solar geometry and photovoltaic generation calculations.
2. Virtanen, P., et al. (2020). [SciPy 1.0: fundamental algorithms for scientific computing in Python](https://doi.org/10.1038/s41592-019-0686-2). *Nature Methods*, 17, 261–272. Used for sparse matrices and the optimization interface; see the [official citation guidance](https://scipy.org/citing-scipy/).
3. Huangfu, Q., and Hall, J. A. J. (2018). [Parallelizing the dual revised simplex method](https://doi.org/10.1007/s12532-017-0130-5). *Mathematical Programming Computation*, 10, 119–142. This is the package citation requested by [HiGHS](https://highs.dev/); the present model selects HiGHS's **interior-point** method through SciPy, rather than claiming to use the paper's simplex algorithm.

The environment also uses NumPy, pandas, Matplotlib, lxml and ReportLab. Dependency versions are in [requirements.txt](../requirements.txt); original run versions are preserved in each optimization summary.

## Weather and market data

4. Sengupta, M., et al. (2018). *The National Solar Radiation Data Base (NSRDB).* *Renewable and Sustainable Energy Reviews*, 89, 51–60. See the [provider's citation guidance](https://www.nlr.gov/hpc/nsrdb-dataset) and [NSRDB portal](https://nsrdb.nlr.gov/). The actual project input is the supplied 2024 Arizona file, identified by its [metadata and checksum](../data/weather/README.md); the reference does not establish a new download or processing history.
5. U.S. Energy Information Administration. [Petroleum spot prices](https://www.eia.gov/dnav/pet/PET_PRI_SPT_S1_D.htm). The saved project snapshot was retrieved September 16, 2026, with a September 10 release and September 9 observations. Gulf Coast jet fuel is a fossil benchmark; diesel and propane are coproduct proxies. [Saved snapshot](../data/prices/eia_spot_prices_2026-09-16.json) and [source HTML](../data/prices/eia_spot_prices_2026-09-16.source.html).

## Equipment and policy references

6. U.S. Department of Energy. [Solar photovoltaic system cost benchmarks](https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks). The model uses the 2025 Q1 benchmark on a 2024-dollar basis. The battery power/energy cost split is a project-derived estimate, not a separate supplier quotation.
7. U.S. Department of Energy, Hydrogen and Fuel Cell Technologies Office (2024). [Multi-Year Program Plan](https://www.energy.gov/sites/default/files/2024-05/hfto-mypp-2024.pdf). Used for the historical installed PEM project-cost estimate.
8. U.S. Department of Energy. [Technical targets for proton exchange membrane electrolysis](https://www.energy.gov/cmei/fuels/technical-targets-proton-exchange-membrane-electrolysis). The model draws on the stated historical status values for efficiency, stack cost and operating life; research targets are not treated as current vendor offers.
9. Internal Revenue Service. [Instructions for Form 8933](https://www.irs.gov/instructions/i8933). Referenced for the treatment of carbon utilization. The model's default policy credit is zero; it does not establish project eligibility.

## Inherited assumptions and attribution

DAC cost basis, synthesis and upgrading costs, storage allowances, several thermal duties, and unquoted coproduct prices remain documented engineering assumptions. References above do not validate those inherited values. See the [audit](model_audit.md) for unit conflicts, source limitations and exclusions.

The MIT license covers original project code and documentation. NSRDB weather, EIA source snapshots and third-party software retain their original ownership and applicable terms. Citing this repository does not replace attribution to those upstream sources.

For the project's own software citation, use [CITATION.cff](../CITATION.cff) and identify the commit and analysis date used.
