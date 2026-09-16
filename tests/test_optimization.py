"""Physical/economic regression tests; run with unittest discover."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from solar_saf.optimization import (build_problem, coefficients, crf, outputs, price_per_kg,
                   product_values, solve, validate, verify)
from solar_saf.solar_resource import read_weather

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT_ROOT / 'config/model_assumptions.json').read_text())
        self.market = json.loads((PROJECT_ROOT / 'config/market_prices.json').read_text())
        self.config['target_saf_kg_per_year'] = 1_000_000
        self.profile = pd.DataFrame({'solar_cf': np.tile([0.0] * 12 + [0.6] * 12, 2)},
                                   index=pd.date_range('2024-01-01', periods=48, freq='h', tz='UTC'))

    def run_case(self, config=None, profile=None):
        config = config or self.config
        validate(config, self.market)
        problem = build_problem(self.profile if profile is None else profile, config, annual_factor=8760 / 48)
        result, _, checks = solve(problem, time_limit=30)
        return problem, result, checks, outputs(problem, result.x, self.market)

    def test_price_units(self):
        record = {'value': 3.785411784 * 0.8, 'unit': 'USD/US_gallon', 'density_kg_per_litre': 0.8}
        self.assertAlmostEqual(price_per_kg(record, self.config), 1)
        self.assertAlmostEqual(crf(0, 25), 0.04)

    def test_cyclic_storage_cannot_create_feedstock_or_electricity(self):
        problem, result, checks, (m, caps, costs, products, ops) = self.run_case()
        self.assertTrue(checks['passed'])
        k = coefficients(self.config)
        self.assertAlmostEqual(m['annual_saf_kg'], 1_000_000, places=3)
        self.assertAlmostEqual(m['annual_h2_kg'], 1_000_000 * k['h2'], places=3)
        self.assertAlmostEqual(m['annual_co2_captured_tonnes'], 1000 * k['co2'], places=3)
        eta = self.config['process']['battery_roundtrip_efficiency'] ** 0.5
        np.testing.assert_allclose(ops.battery_mwh - np.roll(ops.battery_mwh, 1), ops.charge_mw * eta - ops.discharge_mw / eta, atol=1e-6)
        load = ops.electrolyzer_mw + ops.compression_mw + ops.dac_electricity_mw + ops.synthesis_electricity_mw + ops.heater_electricity_mw
        np.testing.assert_allclose(ops.solar_mw + ops.discharge_mw, load + ops.charge_mw + ops.curtail_mw, atol=1e-6)
        self.assertAlmostEqual(costs.annual_cost_usd.sum(), m['annual_net_cost_usd'], places=4)
        self.assertEqual(costs.component.nunique(), len(costs))
        self.assertGreater(caps.set_index('component').loc['battery_energy', 'capacity'], 0)
        self.assertLess(np.minimum(ops.charge_mw, ops.discharge_mw).max(), 1e-5)

    def test_auxiliary_heat_is_supplied_and_paid(self):
        _, _, _, (m, _, _, _, ops) = self.run_case()
        p = self.config['process']
        np.testing.assert_allclose(ops.heater_electricity_mw * p['electric_heater_efficiency'], ops.dac_heat_mwth + ops.high_temperature_heat_mwth, atol=1e-7)
        self.assertTrue((ops.high_temperature_heat_mwth > 0).all())
        self.assertTrue((ops.ft_heat_used_mwth <= ops.co2_tph * p['dac_heat_kwh_per_kg_co2'] + 1e-7).all())
        lower_heat = copy.deepcopy(self.config)
        lower_heat['process']['dac_heat_kwh_per_kg_co2'] = 0
        lower_heat['process']['rwgs_heat_kwh_per_kg_co'] = 0
        lower_heat['process']['upgrading_heat_mj_per_kg_saf'] = 0
        _, _, _, (lower, _, _, _, _) = self.run_case(lower_heat)
        self.assertGreater(m['annual_gross_cost_usd'], lower['annual_gross_cost_usd'])

    def test_turndown_ramp_and_storage_rate_limits(self):
        _, _, _, (_, caps, _, _, ops) = self.run_case()
        cap = caps.set_index('component').capacity / 1000
        p, k = self.config['process'], coefficients(self.config)
        self.assertGreaterEqual(ops.saf_tph.min(), cap.upgrading * p['minimum_turndown_fraction'] - 1e-6)
        self.assertLessEqual(np.abs(ops.saf_tph - np.roll(ops.saf_tph, 1)).max(), cap.upgrading * p['ramp_fraction_per_hour'] + 1e-6)
        self.assertLessEqual(np.abs(ops.h2_tph - k['h2'] * ops.saf_tph).max(), cap.h2_storage * p['h2_storage_flow_fraction_per_hour'] + 1e-6)

    def test_high_oxygen_price_does_not_induce_excess_hydrogen(self):
        self.config['offtake']['oxygen_sales_fraction'] = 1
        self.config['offtake']['oxygen_sales_cap_kg_per_year'] = 1000
        self.market['prices']['oxygen']['value'] = 1000
        _, _, _, (m, _, _, products, _) = self.run_case()
        self.assertAlmostEqual(m['annual_h2_kg'], self.config['target_saf_kg_per_year'] * coefficients(self.config)['h2'], places=3)
        self.assertEqual(products.set_index('product').loc['oxygen', 'sold_kg_per_year'], 1000)

    def test_zero_oxygen_offtake_and_no_automatic_carbon_credit(self):
        products = product_values(self.config, self.market).set_index('product')
        self.assertEqual(products.loc['oxygen', 'net_revenue_usd_per_year'], 0)
        self.assertEqual(self.config['policy']['credit_usd_per_kg_saf'], 0)

    def test_revenue_only_change_preserves_design_and_reconciles(self):
        problem, result, _, before = self.run_case()
        changed = copy.deepcopy(self.config)
        changed['offtake']['diesel_sales_fraction'] = 0
        after_problem = build_problem(self.profile, changed, annual_factor=8760 / 48)
        np.testing.assert_array_equal(problem.objective, after_problem.objective)
        after = outputs(after_problem, result.x, self.market)
        diesel_revenue = before[3].set_index('product').loc['diesel', 'revenue_usd_per_year']
        self.assertAlmostEqual(after[0]['annual_net_cost_usd'] - before[0]['annual_net_cost_usd'], diesel_revenue, places=4)

    def test_cost_increase_cannot_reduce_optimal_gross_cost(self):
        _, _, _, before = self.run_case()
        changed = copy.deepcopy(self.config)
        changed['capital']['solar']['usd_per_unit'] *= 1.5
        _, _, _, after = self.run_case(changed)
        self.assertGreater(after[0]['annual_gross_cost_usd'], before[0]['annual_gross_cost_usd'])

    def test_bad_solution_and_failed_solve_are_rejected(self):
        problem, result, _, _ = self.run_case()
        bad = result.x.copy()
        bad[problem.indices['h2_tph'][0]] += 1
        with self.assertRaises(RuntimeError):
            verify(problem, bad)
        from types import SimpleNamespace
        with patch('solar_saf.optimization.linprog', return_value=SimpleNamespace(success=False, status=1, message='time limit')):
            with self.assertRaisesRegex(RuntimeError, 'did not certify optimality'):
                solve(problem)

    def test_invalid_yields_nan_and_stale_or_future_prices(self):
        for change in ['yield', 'nan', 'stale', 'future']:
            config, market = copy.deepcopy(self.config), copy.deepcopy(self.market)
            if change == 'yield':
                config['process']['product_yields']['saf'] = 0.9
            elif change == 'nan':
                config['capital']['solar']['usd_per_unit'] = float('nan')
            else:
                market['prices']['jet']['observed_on'] = '2026-01-01' if change == 'stale' else '2026-09-17'
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(config, market)

    def test_dac_capacity_conversion(self):
        self.assertEqual(self.config['capital']['dac']['usd_per_unit'], 1100 * 8760 / 1000)

    def test_compressed_weather_matches_plain_csv(self):
        document = ('Time Zone,Local Time Zone,Latitude,Longitude\n0,-7,33.41,-111.94\n'
                    'Year,Month,Day,Hour,Minute,GHI\n2024,1,1,0,0,20\n2024,1,1,1,0,0\n')
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / 'weather.csv'
            compressed = Path(directory) / 'weather.csv.gz'
            plain.write_text(document)
            with gzip.open(compressed, 'wt') as stream:
                stream.write(document)
            plain_meta, plain_data = read_weather(plain)
            gzip_meta, gzip_data = read_weather(compressed)
            self.assertEqual(plain_meta, gzip_meta)
            pd.testing.assert_frame_equal(plain_data, gzip_data)

    def test_nsrdb_uses_data_timezone_not_site_timezone(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weather.csv'
            path.write_text('Time Zone,Local Time Zone,Latitude,Longitude\n0,-7,33.41,-111.94\nYear,Month,Day,Hour,Minute,GHI\n2024,1,1,0,0,20\n2024,1,1,1,0,0\n')
            _, weather = read_weather(path)
            self.assertEqual(weather.index[0].utcoffset().total_seconds(), 0)
            path.write_text(path.read_text().replace('2024,1,1,1,0,0', '2024,1,1,2,0,0'))
            with self.assertRaisesRegex(ValueError, 'uninterrupted hourly'):
                read_weather(path)


if __name__ == '__main__':
    unittest.main()
