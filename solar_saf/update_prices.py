#!/usr/bin/env python3
"""Refresh dated EIA observations while retaining clearly marked unquoted products."""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import ssl
from urllib.request import Request, urlopen

import certifi
from lxml import html

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = 'https://www.eia.gov/dnav/pet/PET_PRI_SPT_S1_D.htm'
SERIES = {'jet': 'EER_EPJK_PF4_RGC_DPG', 'diesel': 'EER_EPD2DXL0_PF4_RGC_DPG',
          'lpg': 'EER_EPLLPA_PF4_Y44MB_DPG'}


def parse_eia(document, as_of):
    tree = html.fromstring(document)
    dates = None
    for row in tree.xpath('//tr'):
        candidates = re.findall(r'\b\d{2}/\d{2}/\d{2}\b', ' '.join(row.itertext()))
        if len(candidates) >= 3:
            dates = [datetime.strptime(item, '%m/%d/%y').date() for item in candidates]
            break
    if not dates or dates != sorted(set(dates)):
        raise ValueError('Could not identify ordered EIA date columns; source layout may have changed')
    observations = {}
    for product, series in SERIES.items():
        anchors = tree.xpath('//a[contains(@href, $series)]', series=series)
        if len(anchors) != 1:
            raise ValueError(f'Expected one exact EIA series link for {product}, found {len(anchors)}')
        row = anchors[0].xpath('ancestor::tr[1]')[0]
        cells = [' '.join(cell.itertext()).strip() for cell in row.xpath('./td')]
        # EIA: leading label cells, one cell per date, then history link.
        values = cells[-len(dates) - 1:-1]
        if len(values) != len(dates):
            raise ValueError(f'EIA date/value column mismatch: {product}')
        valid = []
        for when, value in zip(dates, values):
            if when > as_of:
                continue
            if re.fullmatch(r'\d+\.\d+', value):
                valid.append((when, float(value)))
            elif value not in {'', '-', '--', 'NA', 'N/A', 'W'}:
                raise ValueError(f'Unrecognized EIA value {value!r} for {product}')
        if not valid or (as_of - valid[-1][0]).days > 14:
            raise ValueError(f'No EIA observation within 14 days for {product}')
        when, value = valid[-1]
        observations[product] = {'observed_on': when.isoformat(), 'value': value}
    page = ' '.join(tree.itertext())
    release = re.search(r'(?<!Next )Release Date:\s*(\d{1,2}/\d{1,2}/\d{4})', page)
    if not release:
        raise ValueError('Missing EIA release date')
    released_on = datetime.strptime(release.group(1), '%m/%d/%Y').date()
    if released_on > as_of:
        raise ValueError('This EIA release was published after the requested as-of date')
    next_release = re.search(r'Next Release Date:\s*(\d{1,2}/\d{1,2}/\d{4})', page)
    return observations, released_on.isoformat(), datetime.strptime(next_release.group(1), '%m/%d/%Y').date().isoformat() if next_release else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=date.fromisoformat, default=date.today())
    parser.add_argument('--template', type=Path, default=PROJECT_ROOT / 'config/market_prices.json')
    parser.add_argument('--html', type=Path, help='Parse a previously downloaded source page offline')
    parser.add_argument('--output', type=Path, required=True, help='New snapshot path; existing snapshots are preserved')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Choose a new output filename to preserve the existing snapshot')
    if args.html:
        document = args.html.read_bytes()
    else:
        request = Request(SOURCE, headers={'User-Agent': 'Solar-to-SAF/1.0 public-price-research'})
        with urlopen(request, timeout=45, context=ssl.create_default_context(cafile=certifi.where())) as response:
            document = response.read()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.source.html').write_bytes(document)
    observations, release, next_release = parse_eia(document, args.as_of)
    result = json.loads(args.template.read_text())
    for product, fields in observations.items():
        result['prices'][product].update(fields)
    result.update(as_of=args.as_of.isoformat(), retrieved_on=date.today().isoformat(),
                  release_date=release, next_release_date=next_release, source_url=SOURCE,
                  source_sha256=hashlib.sha256(document).hexdigest())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(observations, indent=2))
    print(f'Saved {args.output}. Set the model config as_of to {args.as_of} before running.')


if __name__ == '__main__':
    main()
