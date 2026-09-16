#!/usr/bin/env python3
"""Run with python -m solar_saf.run_analysis from the project root."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import scipy
import pvlib

from .optimization import build_problem, outputs, solve, validate
from .solar_resource import solar_profile

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def sha256(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def scenarios(base, sensitivity):
    cases = [copy.deepcopy(base)]
    if sensitivity:
        for label, multiplier in [('capital_low_20pct', 0.8), ('capital_high_20pct', 1.2)]:
            c = copy.deepcopy(base)
            c['scenario'] = label
            for item in c['capital'].values():
                item['usd_per_unit'] *= multiplier
            cases.append(c)
        for label, multiplier in [('dac_capital_half', 0.5), ('dac_capital_double', 2.0)]:
            c = copy.deepcopy(base)
            c['scenario'] = label
            c['capital']['dac']['usd_per_unit'] *= multiplier
            cases.append(c)
        c = copy.deepcopy(base)
        c['scenario'] = 'oxygen_100kt_offtake'
        c['offtake']['oxygen_sales_fraction'] = 1
        c['offtake']['oxygen_sales_cap_kg_per_year'] = 100_000_000
        cases.append(c)
        c = copy.deepcopy(base)
        c['scenario'] = 'no_coproduct_sales'
        for name in ['naphtha', 'diesel', 'wax', 'lpg', 'oxygen']:
            c['offtake'][f'{name}_sales_fraction'] = 0
        cases.append(c)
        c = copy.deepcopy(base)
        c['scenario'] = 'legacy_ft_heat_kwh_basis'
        c['process']['ft_recoverable_heat_mj_per_kg_syncrude'] *= 3.6
        cases.append(c)
    return cases


def report_text(summary, capacities):
    m = summary['metrics']
    return '\n'.join([
        '# Final solar-to-SAF model', '',
        f'As of {summary["as_of"]}. Scenario: {summary["scenario"]}.', '',
        f'**Modeled break-even production cost: ${m["lcof_usd_per_kg"]:.2f}/kg SAF** '
        f'(${m["lcof_usd_per_litre"]:.2f}/L; ${m["lcof_usd_per_us_gallon"]:.2f}/US gallon at assumed 0.8 kg/L).', '',
        f'Annual SAF: {m["annual_saf_kg"] / 1e6:,.1f} kt; net annual cost: ${m["annual_net_cost_usd"] / 1e6:,.1f} million; '
        f'installed capital: ${m["installed_capex_usd"] / 1e9:,.2f} billion.', '',
        f'Gross cost before coproducts/support: ${m["gross_lcof_usd_per_kg"]:.2f}/kg. '
        f'Net coproduct revenue: ${m["coproduct_net_revenue_usd_per_year"] / 1e6:.1f} million/year.', '',
        f'Conventional jet benchmark: ${m["fossil_jet_benchmark_usd_per_kg"]:.2f}/kg, observed '
        f'{m["fossil_jet_observed_on"]}. Premium: ${m["premium_to_fossil_jet_usd_per_kg"]:.2f}/kg. '
        'This is a fossil-fuel spot benchmark, not a SAF market quote or a long-term price forecast.', '',
        f'Optimization: {summary["status"]}; {summary["hours"]:,} hourly intervals; '
        f'{summary["solve_seconds"]:.1f} seconds. Independent balance checks passed.', '',
        f'Run scope: **{summary["scope"]}**. Solar output: '
        f'{summary["solar"]["mean_ac_output_per_kwdc"]:.2%} of DC nameplate, or '
        f'{summary["solar"]["mean_ac_capacity_factor"]:.2%} of AC nameplate.', '',
        '## Optimal capacities', '',
        '| Component | Capacity | Unit |', '|---|---:|---|',
        *[f'| {row.component} | {row.capacity:,.1f} | {row.unit} |' for row in capacities.itertuples()], '',
        '## Interpretation', '',
        'Screening optimum for the stated linear-cost technology model, fixed production, and one historical weather year. '
        'Capital estimates use dated benchmarks escalated at an assumed 3% annually. Process equipment, DAC, storage, '
        'some duties, and unquoted coproducts remain engineering assumptions. '
        'Oxygen sales and policy credits are zero in the base case. FT heat supplies low-temperature DAC demand only; '
        'all auxiliary heat draws electricity and has installed heater capacity. '
        'Future forecasts, plant outage scheduling, full process simulation, tax financing, and a verified lifecycle analysis are outside this model.', '',
        '## Price/source notes', '', *['- ' + note for note in summary['notes']], '',
        'Full inputs, source links, version information and SHA-256 hashes are in `model_assumptions_used.json`, '
        '`market_prices_used.json`, and `optimization_summary.json`. Hourly quantities are in `hourly_dispatch.csv`; '
        'the cost breakdown has no subtotal rows that could double-count credits.', ''])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT_ROOT / 'config/model_assumptions.json')
    parser.add_argument('--prices', type=Path, default=PROJECT_ROOT / 'config/market_prices.json')
    parser.add_argument('--solar', type=Path, default=PROJECT_ROOT / 'data/weather/arizona_nsrdb_2024_site_326317.csv.gz')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--hours', type=int, help='Short test only; annual extrapolation is NOT a full-year optimum')
    parser.add_argument('--sensitivity', action='store_true', help='Reoptimize cost/heat cases and evaluate offtake cases')
    parser.add_argument('--time-limit', type=float, default=1200)
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args(argv)
    config, market = json.loads(args.config.read_text()), json.loads(args.prices.read_text())
    validate(config, market)
    profile, solar_meta = solar_profile(args.solar, config)
    if args.hours:
        if not 24 <= args.hours <= len(profile):
            parser.error('--hours must be between 24 and the number of weather records')
        profile = profile.iloc[:args.hours].copy()
        annual_factor, scope = 8760 / len(profile), 'SHORT TEST ONLY: annual extrapolation, not a full-year result'
    else:
        year = profile.index[0].year
        expected = pd.date_range(f'{year}-01-01', f'{year + 1}-01-01', inclusive='left', freq='h', tz=profile.index.tz)
        if not profile.index.equals(expected):
            raise ValueError('Full run requires a complete calendar year of hourly weather')
        annual_factor, scope = 1.0, 'FULL HISTORICAL CALENDAR YEAR'
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.output or PROJECT_ROOT / 'results' / tag
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'run_manifest.json').exists():
        raise FileExistsError(f'{output} already contains a run; choose a new output path')
    manifest = {'status': 'running', 'as_of': config['as_of'], 'created_at_utc': tag, 'scope': scope}
    write_json(output / 'run_manifest.json', manifest)
    fingerprints = {str(path.resolve()): sha256(path) for path in [args.solar, args.config, args.prices, BASE / 'optimization.py', BASE / 'solar_resource.py', Path(__file__)]}
    records = []
    base_solution = None
    try:
        for case in scenarios(config, args.sensitivity):
            notes = validate(case, market)
            name = case['scenario']
            dest = output / name
            dest.mkdir(exist_ok=True)
            print(f'{name}: building {len(profile):,}-hour model ...', flush=True)
            problem = build_problem(profile, case, annual_factor=annual_factor)
            # Exact fixed target + lossless material storage fixes all coproduct
            # quantities. Changing only sales does not change optimal dispatch.
            reused = name in {'oxygen_100kt_offtake', 'no_coproduct_sales'} and base_solution is not None
            if reused:
                result, seconds, verification = base_solution
                seconds = 0.0
            else:
                result, seconds, verification = solve(problem, args.time_limit)
            if base_solution is None:
                base_solution = (result, seconds, verification)
            metrics, capacities, costs, products, ops = outputs(problem, result.x, market)
            summary = {'status': 'optimal', 'scope': scope, 'as_of': case['as_of'], 'scenario': name,
                       'hours': len(profile), 'annualization_factor': annual_factor,
                       'solve_seconds': seconds, 'solver': 'SciPy HiGHS interior point',
                       'solver_message': result.message, 'dispatch_reused_for_constant_revenue_change': reused,
                       'variables': len(result.x), 'constraints': problem.eq.shape[0] + problem.ub.shape[0],
                       'metrics': metrics, 'solar': solar_meta, 'validation': verification, 'notes': notes,
                       'input_code_sha256': fingerprints,
                       'versions': {'python': sys.version.split()[0], 'numpy': np.__version__,
                                    'pandas': pd.__version__, 'scipy': scipy.__version__, 'pvlib': pvlib.__version__}}
            write_json(dest / 'model_assumptions_used.json', case)
            write_json(dest / 'market_prices_used.json', market)
            write_json(dest / 'optimization_summary.json', summary)
            capacities.to_csv(dest / 'optimized_capacities.csv', index=False)
            costs.to_csv(dest / 'cost_breakdown.csv', index=False)
            products.to_csv(dest / 'coproduct_sales.csv', index=False)
            ops.to_csv(dest / 'hourly_dispatch.csv')
            (dest / 'scenario_report.md').write_text(report_text(summary, capacities))
            records.append({'scenario': name, 'scope': scope, 'status': summary['status'], **metrics})
            pd.DataFrame(records).to_csv(output / 'scenario_comparison.csv', index=False)
            print(f'{name}: optimal, ${metrics["lcof_usd_per_kg"]:.4f}/kg SAF; verified; {seconds:.1f}s', flush=True)
        if not args.no_plots:
            from .plot_results import plot_run
            plot_run(output, config['scenario'])
        manifest['status'] = 'complete'
        manifest['scenarios'] = [r['scenario'] for r in records]
        write_json(output / 'run_manifest.json', manifest)
    except Exception as error:
        manifest.update(status='failed', error=str(error))
        write_json(output / 'run_manifest.json', manifest)
        raise
    print(f'Results saved: {output.resolve()}', flush=True)
    return output


if __name__ == '__main__':
    main()
