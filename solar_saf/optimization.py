"""Full-chronology solar-to-SAF LP. Internal units: MW, MWh, tonnes, million USD.

The fixed annual SAF target makes minimizing net annual cost equivalent to
minimizing LCOF. Fixed linear installed costs replace unverified scale curves.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import time

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

GALLON_LITRES = 3.785411784
CAPACITIES = ['solar', 'electrolyzer', 'dac', 'rwgs', 'ft', 'upgrading',
              'h2_storage', 'co2_storage', 'battery_power', 'battery_energy', 'heater']
HOURLY = ['h2_tph', 'co2_tph', 'saf_tph', 'charge_mw', 'discharge_mw',
          'battery_mwh', 'h2_t', 'co2_t', 'dac_heat_mwth', 'curtail_mw']


def crf(rate: float, years: int) -> float:
    return 1 / years if rate == 0 else rate / (1 - (1 + rate) ** -years)


def escalation(config: dict, basis_year: int | None = None) -> float:
    finance = config['finance']
    basis_year = finance['cost_basis_year'] if basis_year is None else basis_year
    years = date.fromisoformat(config['as_of']).year - basis_year
    return (1 + finance['annual_price_escalation_assumption']) ** years


def price_per_kg(record: dict, config: dict) -> float:
    if record['unit'] == 'USD/US_gallon':
        return record['value'] / (GALLON_LITRES * record['density_kg_per_litre'])
    if record['unit'] == 'USD/kg':
        return record['value'] * escalation(config, record.get('price_basis_year', date.fromisoformat(config['as_of']).year))
    raise ValueError(f'Unsupported price unit: {record["unit"]}')


def validate(config: dict, market: dict) -> list[str]:
    def check_numbers(value, trail='config'):
        if isinstance(value, dict):
            for k, v in value.items():
                check_numbers(v, f'{trail}.{k}')
        elif isinstance(value, (float, int)) and not math.isfinite(value):
            raise ValueError(f'Non-finite number: {trail}')
    check_numbers(config)
    check_numbers(market, 'market')
    as_of = date.fromisoformat(config['as_of'])
    if market['as_of'] != config['as_of']:
        raise ValueError('Model and market snapshot as-of dates must agree')
    if date.fromisoformat(market['retrieved_on']) > as_of:
        raise ValueError('Market snapshot retrieved after the analysis as-of date')
    if config['target_saf_kg_per_year'] <= 0:
        raise ValueError('SAF target must be positive')
    f, p, o = config['finance'], config['process'], config['operating']
    if f['project_years'] <= 0 or not 0 <= f['real_discount_rate'] < 1:
        raise ValueError('Invalid finance inputs')
    if not 0 <= f['annual_price_escalation_assumption'] < 1 or f['cost_basis_year'] > as_of.year:
        raise ValueError('Invalid escalation or cost basis year')
    for name, value in p.items():
        if name != 'product_yields' and value < 0:
            raise ValueError(f'Negative process input: {name}')
    for name in ['electrolyzer_kwh_per_kg_h2', 'electric_heater_efficiency',
                 'battery_roundtrip_efficiency', 'h2_storage_flow_fraction_per_hour',
                 'co2_storage_flow_fraction_per_hour']:
        if p[name] <= 0:
            raise ValueError(f'Process input must be positive: {name}')
    for name in ['minimum_turndown_fraction', 'ramp_fraction_per_hour',
                 'ft_heat_recovery_fraction', 'battery_roundtrip_efficiency', 'electric_heater_efficiency']:
        if p[name] > 1:
            raise ValueError(f'Fraction above one: {name}')
    if p['battery_min_hours'] <= 0 or p['battery_max_hours'] < p['battery_min_hours']:
        raise ValueError('Invalid battery duration interval')
    yields = p['product_yields']
    if set(yields) != {'saf', 'naphtha', 'diesel', 'wax', 'lpg'} or any(v < 0 for v in yields.values()) or yields['saf'] <= 0 or not math.isclose(sum(yields.values()), 1, abs_tol=1e-9):
        raise ValueError('Nonnegative product yields must sum to one, including positive SAF')
    if p['rwgs_co2_per_co'] < 44 / 28 - 1e-8 or p['rwgs_h2_per_co'] < 2 / 28 - 1e-8:
        raise ValueError('RWGS fresh CO2/H2 ratios cannot be below stoichiometry')
    solar = config['solar']
    if solar['dc_ac_ratio'] < 1 or not 0 <= solar['system_losses_fraction'] < 1 or not 0 < solar['inverter_efficiency'] <= 1 or not 0 < solar['lifetime_output_factor'] <= 1:
        raise ValueError('Invalid solar parameters')
    if set(config['capital']) != set(CAPACITIES):
        raise ValueError('Capital components do not match model capacities')
    for name, cost in config['capital'].items():
        if cost['usd_per_unit'] <= 0 or cost.get('fixed_opex_fraction', 0) < 0 or cost.get('fixed_opex_usd_per_unit_year', 0) < 0:
            raise ValueError(f'Invalid installed cost: {name}')
    if any(v < 0 for v in o.values()) or o['stack_equivalent_full_load_life_hours'] <= 0:
        raise ValueError('Invalid operating costs or stack life')
    for name, value in config['offtake'].items():
        if name.endswith('_fraction') and not 0 <= value <= 1:
            raise ValueError(f'Invalid sale fraction: {name}')
        if name != 'note' and value < 0:
            raise ValueError(f'Negative offtake value: {name}')
    if config['policy']['credit_usd_per_kg_saf'] < 0:
        raise ValueError('Policy support cannot be negative')
    warnings = []
    for name, record in market['prices'].items():
        if record['value'] < 0:
            raise ValueError(f'Negative price: {name}')
        if 'observed_on' in record:
            age = (as_of - date.fromisoformat(record['observed_on'])).days
            if age < 0:
                raise ValueError(f'Future price observation: {name}')
            if age > 14:
                raise ValueError(f'{name} price is {age} days old; refresh the snapshot')
            if record.get('density_kg_per_litre', 0) <= 0:
                raise ValueError(f'Missing positive density: {name}')
            warnings.append(f'{name}: latest verified observation is {record["observed_on"]} ({age} days before as-of date).')
        else:
            warnings.append(f'{name}: unverified legacy price assumption; no current quote.')
        price_per_kg(record, config)
    if set(market['prices']) != {'jet', 'naphtha', 'diesel', 'wax', 'lpg', 'oxygen'}:
        raise ValueError('Missing or unknown product prices')
    return warnings


def coefficients(config: dict) -> dict:
    p = config['process']
    syn = 1 / p['product_yields']['saf']
    co = syn * p['ft_co_per_syncrude']
    return {'syn': syn, 'co': co, 'co2': co * p['rwgs_co2_per_co'],
            'h2': co * p['rwgs_h2_per_co'] + syn * p['ft_h2_per_syncrude'] + p['upgrading_h2_per_kg_saf'],
            'train_electricity': co * p['rwgs_electricity_kwh_per_kg_co'] + syn * p['ft_electricity_kwh_per_kg_syncrude'] + p['upgrading_electricity_kwh_per_kg_saf'],
            'high_heat': co * p['rwgs_heat_kwh_per_kg_co'] + p['upgrading_heat_mj_per_kg_saf'] / 3.6,
            'recoverable_low_heat': syn * p['ft_recoverable_heat_mj_per_kg_syncrude'] / 3.6 * p['ft_heat_recovery_fraction']}


def product_values(config: dict, market: dict) -> pd.DataFrame:
    target = config['target_saf_kg_per_year']
    yields = config['process']['product_yields']
    records = []
    for name in ['naphtha', 'diesel', 'wax', 'lpg', 'oxygen']:
        mass = target * (8 * coefficients(config)['h2'] if name == 'oxygen' else yields[name] / yields['saf'])
        sold = mass * config['offtake'][f'{name}_sales_fraction']
        if name == 'oxygen':
            sold = min(sold, config['offtake']['oxygen_sales_cap_kg_per_year'])
        price = price_per_kg(market['prices'][name], config)
        conditioning = sold * config['offtake']['oxygen_conditioning_usd_per_kg_sold'] * escalation(config) if name == 'oxygen' else 0
        records.append({'product': name, 'produced_kg_per_year': mass, 'sold_kg_per_year': sold,
                        'unsold_kg_per_year': mass - sold, 'price_usd_per_kg': price,
                        'revenue_usd_per_year': sold * price, 'conditioning_usd_per_year': conditioning,
                        'net_revenue_usd_per_year': sold * price - conditioning,
                        'price_status': market['prices'][name]['status']})
    return pd.DataFrame(records)


class Rows:
    def __init__(self, nvars):
        self.nvars, self.row, self.col, self.val, self.rhs, self.names = nvars, [], [], [], [], []

    def add(self, name, terms, rhs=0):
        i = len(self.rhs)
        for j, value in terms:
            if value:
                self.row.append(i)
                self.col.append(j)
                self.val.append(value)
        self.rhs.append(rhs)
        self.names.append(name)

    def matrix(self):
        return coo_matrix((self.val, (self.row, self.col)), shape=(len(self.rhs), self.nvars)).tocsr()


@dataclass
class Problem:
    objective: np.ndarray
    eq: object
    eq_rhs: np.ndarray
    ub: object
    ub_rhs: np.ndarray
    eq_names: list
    ub_names: list
    indices: dict
    capital_costs: dict
    annual_factor: float
    config: dict
    profile: pd.DataFrame


def build_problem(profile: pd.DataFrame, config: dict, *, annual_factor=1.0) -> Problem:
    n = len(profile)
    cf = profile.solar_cf.to_numpy(dtype=float)
    if n < 2 or not np.isfinite(cf).all() or cf.min() < 0 or cf.max() > 1 or cf.mean() <= 0:
        raise ValueError('Invalid solar profile')
    if not np.isfinite(annual_factor) or annual_factor <= 0:
        raise ValueError('Invalid annualization factor')
    idx = {name: i for i, name in enumerate(CAPACITIES)}
    idx.update({name: np.arange(len(CAPACITIES) + k * n, len(CAPACITIES) + (k + 1) * n) for k, name in enumerate(HOURLY)})
    nv = len(CAPACITIES) + len(HOURLY) * n
    eq, ub = Rows(nv), Rows(nv)
    c = np.zeros(nv)
    p, o, finance = config['process'], config['operating'], config['finance']
    k, esc = coefficients(config), escalation(config)
    recovery = crf(finance['real_discount_rate'], finance['project_years'])
    capital_costs = {}
    for name in CAPACITIES:
        cost = config['capital'][name]
        installed = cost['usd_per_unit'] * esc
        if name in {'dac', 'rwgs', 'ft', 'upgrading', 'heater'}:
            installed *= 1 + o['process_contingency_fraction']
        fixed = cost.get('fixed_opex_usd_per_unit_year', 0) * esc + installed * cost.get('fixed_opex_fraction', 0)
        replacement = 0
        if name == 'battery_energy' and 0 < o['battery_replacement_year'] < finance['project_years']:
            replacement = installed * o['battery_replacement_fraction'] / (1 + finance['real_discount_rate']) ** o['battery_replacement_year']
        capital_costs[name] = {'installed': installed, 'annualized': installed * recovery,
                               'fixed': fixed, 'replacement': replacement * recovery}
        # One MW / tonne per hour / tonne contains 1000 corresponding base units.
        c[idx[name]] = (installed * recovery + fixed + replacement * recovery) / 1000
    h2_var = esc * (p['water_kg_per_kg_h2'] * o['water_usd_per_kg'] + p['electrolyzer_kwh_per_kg_h2'] * o['stack_replacement_usd_per_kw'] / o['stack_equivalent_full_load_life_hours'])
    c[idx['h2_tph']] = h2_var / 1000 * annual_factor
    c[idx['co2_tph']] = esc * o['dac_sorbent_usd_per_tco2'] / 1e6 * annual_factor
    c[idx['saf_tph']] = esc * o['catalyst_usd_per_kg_saf'] / 1000 * annual_factor
    for name in ['charge_mw', 'discharge_mw']:
        c[idx[name]] = esc * o['battery_throughput_usd_per_kwh'] / 1000 * annual_factor
    eta = math.sqrt(p['battery_roundtrip_efficiency'])
    for t in range(n):
        prev = (t - 1) % n
        h, d, s = idx['h2_tph'][t], idx['co2_tph'][t], idx['saf_tph'][t]
        ch, dis = idx['charge_mw'][t], idx['discharge_mw'][t]
        b, hs, ds, heat = idx['battery_mwh'][t], idx['h2_t'][t], idx['co2_t'][t], idx['dac_heat_mwth'][t]
        eq.add('electricity_MW', [(idx['solar'], cf[t]), (dis, 1),
               (h, -(p['electrolyzer_kwh_per_kg_h2'] + p['h2_compression_kwh_per_kg'])),
               (d, -(p['dac_electricity_kwh_per_kg_co2'] + p['co2_compression_kwh_per_kg'])),
               (s, -(k['train_electricity'] + k['high_heat'] / p['electric_heater_efficiency'])),
               (heat, -1 / p['electric_heater_efficiency']), (ch, -1), (idx['curtail_mw'][t], -1)])
        eq.add('h2_balance_t', [(hs, 1), (idx['h2_t'][prev], -1), (h, -1), (s, k['h2'])])
        eq.add('co2_balance_t', [(ds, 1), (idx['co2_t'][prev], -1), (d, -1), (s, k['co2'])])
        eq.add('battery_balance_MWh', [(b, 1), (idx['battery_mwh'][prev], -1), (ch, -eta), (dis, 1 / eta)])
        ub.add('low_temperature_heat_MWth', [(d, p['dac_heat_kwh_per_kg_co2']), (s, -k['recoverable_low_heat']), (heat, -1)])
        for name, var, factor in [('electrolyzer', h, p['electrolyzer_kwh_per_kg_h2']),
                                  ('dac', d, 1), ('rwgs', s, k['co']), ('ft', s, k['syn']),
                                  ('upgrading', s, 1), ('h2_storage', hs, 1),
                                  ('co2_storage', ds, 1), ('battery_energy', b, 1)]:
            ub.add(f'capacity_{name}', [(var, factor), (idx[name], -1)])
        ub.add('heater_capacity_MWth', [(heat, 1), (s, k['high_heat']), (idx['heater'], -1)])
        ub.add('battery_power_MW', [(ch, 1), (dis, 1), (idx['battery_power'], -1)])
        ub.add('turndown_tph', [(idx['upgrading'], p['minimum_turndown_fraction']), (s, -1)])
        for direction in [-1, 1]:
            ub.add('ramp_tph', [(s, direction), (idx['saf_tph'][prev], -direction), (idx['upgrading'], -p['ramp_fraction_per_hour'])])
            ub.add('h2_storage_flow_tph', [(h, direction), (s, -direction * k['h2']), (idx['h2_storage'], -p['h2_storage_flow_fraction_per_hour'])])
            ub.add('co2_storage_flow_tph', [(d, direction), (s, -direction * k['co2']), (idx['co2_storage'], -p['co2_storage_flow_fraction_per_hour'])])
    eq.add('annual_saf_tonnes', [(j, annual_factor) for j in idx['saf_tph']], config['target_saf_kg_per_year'] / 1000)
    ub.add('battery_min_duration_MWh', [(idx['battery_power'], p['battery_min_hours']), (idx['battery_energy'], -1)])
    ub.add('battery_max_duration_MWh', [(idx['battery_energy'], 1), (idx['battery_power'], -p['battery_max_hours'])])
    return Problem(c, eq.matrix(), np.array(eq.rhs), ub.matrix(), np.array(ub.rhs),
                   eq.names, ub.names, idx, capital_costs, annual_factor, config, profile)


def solve(problem: Problem, time_limit=1200):
    start = time.monotonic()
    result = linprog(problem.objective, A_ub=problem.ub, b_ub=problem.ub_rhs,
                     A_eq=problem.eq, b_eq=problem.eq_rhs, bounds=(0, None),
                     method='highs-ipm', options={'time_limit': time_limit,
                     'primal_feasibility_tolerance': 1e-7, 'dual_feasibility_tolerance': 1e-7,
                     'ipm_optimality_tolerance': 1e-8})
    seconds = time.monotonic() - start
    if not result.success or result.status != 0:
        raise RuntimeError(f'Solver did not certify optimality (status {result.status}): {result.message}')
    validation = verify(problem, result.x)
    validation['objective_reconciliation_usd'] = abs(float(problem.objective @ result.x - result.fun)) * 1e6
    return result, seconds, validation


def verify(problem: Problem, x: np.ndarray) -> dict:
    if not np.isfinite(x).all():
        raise RuntimeError('Non-finite solution')
    equality = np.abs(problem.eq @ x - problem.eq_rhs)
    inequality = np.maximum(problem.ub @ x - problem.ub_rhs, 0)
    checks = {}
    for names, violations in [(problem.eq_names, equality), (problem.ub_names, inequality)]:
        for name, error in zip(names, violations):
            checks[name] = max(checks.get(name, 0), float(error))
    checks['nonnegative_variables'] = max(0.0, -float(x.min()))
    simultaneous = float(np.minimum(x[problem.indices['charge_mw']], x[problem.indices['discharge_mw']]).max())
    checks['simultaneous_battery_charge_discharge_MW'] = simultaneous
    if max(checks.values()) > 1e-4:
        raise RuntimeError(f'Solution failed physical verification: {checks}')
    return {'passed': True, 'absolute_tolerance_internal_units': 1e-4, 'max_violations': checks}


def outputs(problem: Problem, x: np.ndarray, market: dict):
    config, idx = problem.config, problem.indices
    p, o, k = config['process'], config['operating'], coefficients(config)
    esc, af = escalation(config), problem.annual_factor
    target = config['target_saf_kg_per_year']
    capacities, costs = [], []
    for name in CAPACITIES:
        value = float(x[idx[name]]) * 1000
        unit = config['capital'][name]['unit']
        capacities.append({'component': name, 'capacity': value, 'unit': unit})
        cp = problem.capital_costs[name]
        costs.append({'component': name, 'installed_capex_usd': value * cp['installed'],
                      'annualized_capex_usd': value * cp['annualized'],
                      'fixed_opex_usd_per_year': value * cp['fixed'],
                      'replacement_reserve_usd_per_year': value * cp['replacement'],
                      'annual_cost_usd': value * (cp['annualized'] + cp['fixed'] + cp['replacement'])})
    h2_kg = float(x[idx['h2_tph']].sum()) * 1000 * af
    co2_tonnes = float(x[idx['co2_tph']].sum()) * af
    extras = {
        'water': h2_kg * p['water_kg_per_kg_h2'] * o['water_usd_per_kg'] * esc,
        'stack_replacement_reserve': h2_kg * p['electrolyzer_kwh_per_kg_h2'] * o['stack_replacement_usd_per_kw'] / o['stack_equivalent_full_load_life_hours'] * esc,
        'dac_sorbent': co2_tonnes * o['dac_sorbent_usd_per_tco2'] * esc,
        'catalyst': target * o['catalyst_usd_per_kg_saf'] * esc,
        'battery_throughput': float((x[idx['charge_mw']] + x[idx['discharge_mw']]).sum()) * 1000 * af * o['battery_throughput_usd_per_kwh'] * esc}
    products = product_values(config, market)
    for row in products.to_dict('records'):
        extras[f'{row["product"]}_revenue'] = -row['revenue_usd_per_year']
        if row['conditioning_usd_per_year']:
            extras[f'{row["product"]}_conditioning'] = row['conditioning_usd_per_year']
    extras['policy_support'] = -target * config['policy']['credit_usd_per_kg_saf']
    for name, annual in extras.items():
        costs.append({'component': name, 'installed_capex_usd': 0, 'annualized_capex_usd': 0,
                      'fixed_opex_usd_per_year': 0, 'replacement_reserve_usd_per_year': 0,
                      'annual_cost_usd': annual})
    costs = pd.DataFrame(costs)
    costs['lcof_usd_per_kg'] = costs.annual_cost_usd / target
    ops = problem.profile.copy()
    for name in HOURLY:
        ops[name] = x[idx[name]]
    ops['solar_mw'] = ops.solar_cf * x[idx['solar']]
    ops['electrolyzer_mw'] = ops.h2_tph * p['electrolyzer_kwh_per_kg_h2']
    ops['compression_mw'] = ops.h2_tph * p['h2_compression_kwh_per_kg'] + ops.co2_tph * p['co2_compression_kwh_per_kg']
    ops['dac_electricity_mw'] = ops.co2_tph * p['dac_electricity_kwh_per_kg_co2']
    ops['synthesis_electricity_mw'] = ops.saf_tph * k['train_electricity']
    ops['high_temperature_heat_mwth'] = ops.saf_tph * k['high_heat']
    ops['heater_electricity_mw'] = (ops.dac_heat_mwth + ops.high_temperature_heat_mwth) / p['electric_heater_efficiency']
    ops['ft_heat_used_mwth'] = np.minimum(ops.co2_tph * p['dac_heat_kwh_per_kg_co2'], ops.saf_tph * k['recoverable_low_heat'])
    ops['co_tph'] = ops.saf_tph * k['co']
    ops['syncrude_tph'] = ops.saf_tph * k['syn']
    annual = float(costs.annual_cost_usd.sum())
    gross = float(problem.objective @ x) * 1e6
    expected_net = gross - float(products.net_revenue_usd_per_year.sum()) + extras['policy_support']
    if not math.isclose(annual, expected_net, rel_tol=1e-8, abs_tol=0.05):
        raise RuntimeError('Exported cost breakdown does not reconcile to solver objective')
    jet = price_per_kg(market['prices']['jet'], config)
    metrics = {'lcof_usd_per_kg': annual / target,
               'lcof_usd_per_litre': annual / target * market['prices']['jet']['density_kg_per_litre'],
               'lcof_usd_per_us_gallon': annual / target * market['prices']['jet']['density_kg_per_litre'] * GALLON_LITRES,
               'gross_lcof_usd_per_kg': gross / target,
               'annual_net_cost_usd': annual, 'annual_gross_cost_usd': gross,
               'installed_capex_usd': float(costs.installed_capex_usd.sum()),
               'annual_saf_kg': float(ops.saf_tph.sum()) * 1000 * af,
               'annual_h2_kg': h2_kg, 'annual_co2_captured_tonnes': co2_tonnes,
               'coproduct_net_revenue_usd_per_year': float(products.net_revenue_usd_per_year.sum()),
               'fossil_jet_benchmark_usd_per_kg': jet,
               'fossil_jet_observed_on': market['prices']['jet']['observed_on'],
               'premium_to_fossil_jet_usd_per_kg': annual / target - jet,
               'solar_curtailment_fraction': float(ops.curtail_mw.sum() / ops.solar_mw.sum()),
               'annual_electricity_consumption_kwh_per_kg_saf': float((ops.electrolyzer_mw + ops.compression_mw + ops.dac_electricity_mw + ops.synthesis_electricity_mw + ops.heater_electricity_mw).sum()) * 1000 * af / target,
               'battery_duration_hours': float(x[idx['battery_energy']] / x[idx['battery_power']]) if x[idx['battery_power']] > 1e-8 else 0}
    return metrics, pd.DataFrame(capacities), costs, products, ops
