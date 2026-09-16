"""Strict NSRDB reader and PVWatts output in kW AC per installed kW DC."""
from __future__ import annotations

import csv
import gzip
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pvlib import inverter, irradiance, pvsystem, temperature
from pvlib.location import Location

TIME_COLUMNS = ['Year', 'Month', 'Day', 'Hour', 'Minute']
WEATHER_COLUMNS = ['DNI', 'GHI', 'DHI', 'Temperature', 'Wind Speed',
                   'Panel Tilt', 'Panel Azimuth Angle', 'Surface Albedo',
                   'Solar Zenith Angle', 'Capacity Factor']


def read_weather(path: Path) -> tuple[dict, pd.DataFrame]:
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, mode='rt', newline='', encoding='utf-8-sig') as stream:
        rows = csv.reader(stream)
        preamble = []
        for i, row in enumerate(rows):
            row = [v.strip() for v in row]
            if row and row[0] == 'Year':
                header = i
                break
            preamble.append(row)
            if i >= 29:
                raise ValueError('NSRDB Year header missing in first 30 rows')
        else:
            raise ValueError('Empty NSRDB data')
    metadata = dict(zip(*preamble[:2])) if len(preamble) >= 2 else {}
    if 'Time Zone' not in metadata:
        raise ValueError('NSRDB Time Zone is required; Local Time Zone is not the timestamp zone')
    data = pd.read_csv(path, skiprows=header,
                       usecols=lambda c: c in TIME_COLUMNS + WEATHER_COLUMNS)
    times = pd.DatetimeIndex(pd.to_datetime(data[TIME_COLUMNS].rename(columns=str.lower)))
    times = times.tz_localize(timezone(timedelta(hours=float(metadata['Time Zone']))))
    if times.has_duplicates or not times.is_monotonic_increasing or len(times) < 2:
        raise ValueError('Timestamps must be unique, ordered, and contain at least two hours')
    if not np.all(np.diff(times.asi8) == pd.Timedelta(hours=1).value):
        raise ValueError('Expected uninterrupted hourly data; missing/subhourly rows must be resolved')
    data.index = times
    for c in WEATHER_COLUMNS:
        if c in data:
            data[c] = pd.to_numeric(data[c], errors='coerce').replace([-9999, -9900, -999, -99], np.nan)
    return metadata, data


def solar_profile(path: Path, config: dict) -> tuple[pd.DataFrame, dict]:
    metadata, data = read_weather(path)
    solar = config['solar']
    ilr = solar['dc_ac_ratio']
    if 'Capacity Factor' in data:
        cf = data['Capacity Factor']
        if cf.isna().any() or not cf.between(0, 1 / ilr + 1e-9).all():
            raise ValueError('Capacity Factor must be finite AC kW / DC nameplate kW, within inverter rating')
        method = 'provided_ac_output_per_kwdc; supplied profile includes all losses'
        zenith_error = None
    else:
        required = ['DNI', 'GHI', 'DHI', 'Temperature', 'Wind Speed']
        if not set(required).issubset(data):
            raise ValueError(f'Missing weather columns: {set(required) - set(data)}')
        if data[required].isna().any().any():
            raise ValueError('Missing irradiance/temperature/wind values; no silent weather imputation')
        if (data[['DNI', 'GHI', 'DHI', 'Wind Speed']] < 0).any().any():
            raise ValueError('Negative irradiance or wind speed')
        site = Location(float(metadata['Latitude']), float(metadata['Longitude']),
                        tz=data.index.tz, altitude=float(metadata.get('Elevation', 0)))
        position = site.get_solarposition(data.index)
        # NSRDB omits tracker angles at twilight, including a few 6-7 W/m2
        # observations. Stow those rows horizontally; never forward-fill a
        # previous day's tracker angle. Missing substantive daylight is an error.
        daylight = data['GHI'] > 20
        zenith_error = None
        if 'Solar Zenith Angle' in data:
            valid = daylight & data['Solar Zenith Angle'].notna()
            zenith_error = float((position.apparent_zenith[valid] - data['Solar Zenith Angle'][valid]).abs().median())
            if not np.isfinite(zenith_error) or zenith_error > 5:
                raise ValueError('Solar geometry disagrees with NSRDB: check timestamp timezone')
        for c in ['Panel Tilt', 'Panel Azimuth Angle']:
            if c not in data or data.loc[daylight, c].isna().any():
                raise ValueError(f'Missing daylight {c}')
        tilt = data['Panel Tilt'].fillna(0)
        azimuth = data['Panel Azimuth Angle'].fillna(180)
        if not tilt.between(0, 90).all() or not azimuth.between(0, 360).all():
            raise ValueError('Invalid tracker angles')
        albedo = data['Surface Albedo'].fillna(0.2) if 'Surface Albedo' in data else 0.2
        poa = irradiance.get_total_irradiance(
            tilt, azimuth, position.apparent_zenith, position.azimuth,
            data.DNI, data.GHI, data.DHI, albedo=albedo)['poa_global'].clip(lower=0)
        cell_temp = temperature.sapm_cell(poa, data.Temperature, data['Wind Speed'],
                                           a=-3.56, b=-0.075, deltaT=3)
        dc = pvsystem.pvwatts_dc(poa, cell_temp, pdc0=1,
                                 gamma_pdc=solar['temperature_coefficient_per_c'])
        dc *= (1 - solar['system_losses_fraction']) * solar['lifetime_output_factor']
        cf = inverter.pvwatts(dc, pdc0=1 / (ilr * solar['inverter_efficiency']),
                             eta_inv_nom=solar['inverter_efficiency']).clip(lower=0)
        cf = cf.where(data.GHI > 0, 0)
        method = 'pvlib_pvwatts_single_axis_ac_output_per_kwdc'
    if not np.isfinite(cf).all() or cf.mean() <= 0:
        raise ValueError('Solar profile contains invalid values or no generation')
    profile = pd.DataFrame({'solar_cf': cf}, index=data.index)
    profile.index.name = 'timestamp'
    meta = {'source_file': str(Path(path).resolve()), 'weather_year': int(data.index[0].year),
            'hours': len(data), 'timestamp_timezone': str(data.index.tz),
            'site_local_timezone_offset': metadata.get('Local Time Zone'),
            'latitude': float(metadata.get('Latitude', 'nan')),
            'longitude': float(metadata.get('Longitude', 'nan')),
            'method': method, 'mean_ac_output_per_kwdc': float(cf.mean()),
            'mean_ac_capacity_factor': float(cf.mean() * ilr),
            'twilight_rows_with_stowed_tracker': int(((data.GHI > 0) & data['Panel Tilt'].isna()).sum()) if 'Panel Tilt' in data else 0,
            'median_daylight_zenith_error_degrees': zenith_error}
    return profile, meta
