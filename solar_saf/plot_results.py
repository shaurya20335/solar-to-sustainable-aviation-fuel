"""Generate shareable figures from solved outputs only; no embedded model results."""
import argparse
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'solar-saf-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_run(root: Path, base_scenario='current_base'):
    root = Path(root)
    dest = root / 'figures'
    dest.mkdir(exist_ok=True)
    summary = json.loads((root / base_scenario / 'optimization_summary.json').read_text())
    costs = pd.read_csv(root / base_scenario / 'cost_breakdown.csv')
    ops = pd.read_csv(root / base_scenario / 'hourly_dispatch.csv', index_col=0, parse_dates=True)
    comparison = pd.read_csv(root / 'scenario_comparison.csv')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.dpi': 180})
    def save(fig, name):
        for ext in ['png', 'pdf']:
            fig.savefig(dest / f'{name}.{ext}', bbox_inches='tight', facecolor='white')
        plt.close(fig)

    m = summary['metrics']
    fig, ax = plt.subplots(figsize=(10, 7))
    frame = costs[costs.lcof_usd_per_kg.abs() >= 0.005].sort_values('lcof_usd_per_kg')
    bars = ax.barh(frame.component.str.replace('_', ' '), frame.lcof_usd_per_kg,
                   color=np.where(frame.lcof_usd_per_kg >= 0, '#246b80', '#dc9031'))
    ax.bar_label(bars, fmt='%.2f', padding=4, fontsize=9)
    ax.axvline(0, color='#555555', linewidth=0.7)
    ax.set_xlim(min(-1, frame.lcof_usd_per_kg.min() * 1.4), frame.lcof_usd_per_kg.max() * 1.2)
    ax.set_xlabel('Contribution to break-even production cost (USD/kg SAF)')
    ax.set_title(f'Final model: ${m["lcof_usd_per_kg"]:.2f}/kg SAF | {summary["as_of"]}', loc='left', weight='bold')
    fig.text(0.01, -0.025, 'Engineering screening estimate; dated market observations and explicit cost assumptions.\n'
             + summary['scope'], fontsize=8, color='#555555')
    fig.tight_layout()
    save(fig, '01_cost_breakdown')

    fig, ax = plt.subplots(figsize=(10, 5))
    frame = comparison.sort_values('lcof_usd_per_kg')
    bars = ax.barh(frame.scenario.str.replace('_', ' '), frame.lcof_usd_per_kg,
                   color=['#dc9031' if s == base_scenario else '#246b80' for s in frame.scenario])
    ax.bar_label(bars, fmt='$%.2f', padding=4)
    ax.set_xlim(0, frame.lcof_usd_per_kg.max() * 1.16)
    ax.axvline(m['fossil_jet_benchmark_usd_per_kg'], color='#555555', linestyle='--',
               label=f'Fossil jet spot proxy ({m["fossil_jet_observed_on"]})')
    ax.set_xlabel('Modeled break-even production cost (USD/kg SAF)')
    ax.set_title('Assumption sensitivity — each cost case reoptimized', loc='left', weight='bold')
    ax.legend(loc='lower right', frameon=False, fontsize=8)
    fig.text(0.01, -0.025, 'Scenarios are conditional estimates, not a statistical confidence interval. Offtake cases retain the same optimal dispatch.', fontsize=8)
    fig.tight_layout()
    save(fig, '02_sensitivity')

    # Cold-season sample week; output timestamps remain explicitly UTC.
    week = ops.iloc[0:min(168, len(ops))]
    hour = np.arange(len(week))
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(hour, week.solar_mw, color='#dc9031', label='Solar AC generation')
    axes[0].plot(hour, week.electrolyzer_mw, color='#246b80', label='Electrolyzer')
    axes[0].plot(hour, week.heater_electricity_mw, color='#a44b69', label='Electric heating')
    axes[0].set_ylabel('MW')
    axes[0].legend(ncol=3, frameon=False, fontsize=9)
    axes[1].plot(hour, week.battery_mwh, color='#507e52', label='Battery state of charge')
    axes[1].set_ylabel('MWh')
    axes[1].legend(frameon=False)
    axes[2].plot(hour, week.saf_tph, color='#246b80', label='SAF production')
    axes[2].set_ylabel('Tonnes SAF/hour')
    axes[2].set_xlabel(f'Hours from {week.index[0]}')
    axes[2].legend(frameon=False)
    for ax in axes:
        ax.grid(alpha=0.15)
    axes[0].set_title('Hourly dispatch: all electric heating is included', loc='left', weight='bold')
    fig.tight_layout()
    save(fig, '03_hourly_dispatch')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    monthly = ops.resample('MS').agg({'solar_cf': 'mean', 'saf_tph': 'sum'})
    axes[0].bar(monthly.index.strftime('%b'), monthly.solar_cf * 100, color='#dc9031')
    axes[0].set_ylabel('AC output / DC nameplate (%)')
    axes[0].set_title('Corrected solar resource', loc='left', weight='bold')
    axes[1].bar(monthly.index.strftime('%b'), monthly.saf_tph / 1000, color='#246b80')
    axes[1].set_ylabel('Thousand tonnes SAF')
    axes[1].set_title('Production by calendar month', loc='left', weight='bold')
    fig.tight_layout()
    save(fig, '04_monthly_production')
    print(f'Figures saved: {dest}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--scenario', default='current_base')
    args = parser.parse_args()
    plot_run(args.run_directory, args.scenario)
