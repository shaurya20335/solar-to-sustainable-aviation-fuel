"""Price-feed tests exercise holiday gaps, dates and series selection."""
from datetime import date
import json
from pathlib import Path
import unittest

from solar_saf.update_prices import parse_eia, SERIES

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PriceFeedTests(unittest.TestCase):
    def fixture(self):
        rows = ['<tr><td>Product</td><td>09/04/26</td><td>09/07/26</td><td>09/08/26</td><td>History</td></tr>']
        for product, series in SERIES.items():
            rows.append(f'<tr><td>{product}</td><td>1.100</td><td>&nbsp;</td><td>1.250</td><td><a href="?s={series}&amp;f=D">History</a></td></tr>')
        return '<html><table>' + ''.join(rows) + '</table><p>Release Date: 9/9/2026</p><p>Next Release Date: 9/16/2026</p></html>'

    def test_holiday_columns_keep_date_alignment(self):
        values, release, next_release = parse_eia(self.fixture(), date(2026, 9, 16))
        self.assertEqual(values['jet'], {'observed_on': '2026-09-08', 'value': 1.25})
        self.assertEqual(release, '2026-09-09')
        self.assertEqual(next_release, '2026-09-16')

    def test_newer_publication_not_used_in_historical_analysis(self):
        with self.assertRaisesRegex(ValueError, 'published after'):
            parse_eia(self.fixture(), date(2026, 9, 8))

    def test_missing_series_and_bad_values_fail_closed(self):
        for document in [self.fixture().replace(SERIES['jet'], 'OTHER'),
                         self.fixture().replace('1.250', 'bad-value')]:
            with self.assertRaises(ValueError):
                parse_eia(document, date(2026, 9, 16))

    def test_cached_live_source_matches_checked_model_snapshot(self):
        source = PROJECT_ROOT / 'data/prices/eia_spot_prices_2026-09-16.source.html'
        if not source.exists():
            self.skipTest('Optional cached EIA source not present')
        observations, _, _ = parse_eia(source.read_bytes(), date(2026, 9, 16))
        expected = json.loads((PROJECT_ROOT / 'config/market_prices.json').read_text())['prices']
        for product, fields in observations.items():
            self.assertEqual(fields['observed_on'], expected[product]['observed_on'])
            self.assertEqual(fields['value'], expected[product]['value'])


if __name__ == '__main__':
    unittest.main()
