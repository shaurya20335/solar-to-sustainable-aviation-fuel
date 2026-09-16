"""Create a shareable PDF from a completed run, including sensitivity results."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image


def build_report(root):
    root = Path(root)
    manifest = json.loads((root / 'run_manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError('PDF report requires a completed run')
    base = root / manifest['scenarios'][0]
    result = json.loads((base / 'optimization_summary.json').read_text())
    m = result['metrics']
    config = json.loads((base / 'model_assumptions_used.json').read_text())
    caps = pd.read_csv(base / 'optimized_capacities.csv').set_index('component').capacity
    cases = pd.read_csv(root / 'scenario_comparison.csv')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Deck', fontName='Helvetica', fontSize=12, leading=17, textColor=colors.HexColor('#34546a'), spaceAfter=14))
    styles.add(ParagraphStyle(name='SmallNote', fontName='Helvetica', fontSize=8, leading=11, spaceAfter=8))
    styles['BodyText'].spaceAfter = 8
    styles['BodyText'].leading = 14
    styles['Title'].alignment = TA_LEFT
    story = []

    def para(text, style='BodyText'):
        story.append(Paragraph(text, styles[style]))

    def table(rows, widths):
        cells = [[Paragraph(escape(str(cell)), styles['SmallNote']) for cell in row] for row in rows]
        obj = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        obj.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dceaf0')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#246b80')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f7f8')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        story.append(obj)
        story.append(Spacer(1, 12))

    para('Solar-to-SAF: Final Model', 'Title')
    para(f'Cost assessment as of {result["as_of"]}<br/>Arizona | 100,000 tonnes SAF/year | Solar-to-SAF', 'Deck')
    para(f'<b>Base modeled production cost: ${m["lcof_usd_per_kg"]:.2f}/kg SAF</b>', 'Heading1')
    para(f'Equivalent to ${m["lcof_usd_per_litre"]:.2f}/litre and ${m["lcof_usd_per_us_gallon"]:.2f}/US gallon under the stated density assumption. '
         'This is a break-even engineering estimate, not an observed SAF market quotation.')
    table([['Measure', 'Result'],
           ['Annual net production cost', f'${m["annual_net_cost_usd"] / 1e6:,.1f} million'],
           ['Installed capital', f'${m["installed_capex_usd"] / 1e9:,.2f} billion'],
           ['Gross cost before coproducts/support', f'${m["gross_lcof_usd_per_kg"]:.2f}/kg'],
           ['Net coproduct revenue', f'${m["coproduct_net_revenue_usd_per_year"] / 1e6:.1f} million/year'],
           ['Conventional jet benchmark', f'${m["fossil_jet_benchmark_usd_per_kg"]:.2f}/kg, observed {m["fossil_jet_observed_on"]}'],
           ['Model premium to that spot benchmark', f'${m["premium_to_fossil_jet_usd_per_kg"]:.2f}/kg'],
           ['Weather chronology', f'{result["hours"]:,} hours; {result["scope"]}']], [260, 250])
    para('Selected optimal capacities', 'Heading2')
    table([['Equipment', 'Capacity'],
           ['Solar PV', f'{caps.solar/1e6:.3f} GW DC'],
           ['Electrolyzer', f'{caps.electrolyzer/1e6:.3f} GW'],
           ['DAC capture', f'{caps.dac/1000:.1f} tonnes/hour'],
           ['Battery', f'{caps.battery_power/1000:.1f} MW / {caps.battery_energy/1000:.1f} MWh'],
           ['Hydrogen storage', f'{caps.h2_storage/1000:.1f} tonnes'],
           ['SAF upgrading', f'{caps.upgrading/1000:.2f} tonnes/hour']], [260, 250])
    para('The base case has no oxygen revenue and no policy credit. Liquid coproduct sales use a 90% saleable-volume assumption. '
         'Equipment costs combine dated public benchmarks and explicitly identified engineering assumptions.', 'SmallNote')

    story.append(PageBreak())
    para('Sensitivity to assumptions', 'Title')
    table([['Scenario', 'Cost (USD/kg SAF)', 'Solver status']] +
          [[row.scenario.replace('_', ' '), f'{row.lcof_usd_per_kg:.2f}', row.status] for row in cases.itertuples()], [310, 110, 90])
    para('Each equipment-cost or heat case was reoptimized over the full chronology. Offtake changes affect constant revenue only, '
         'so those cases reuse the identical optimal design. These cases are conditional scenarios, not a statistical confidence interval. '
         'The legacy FT heat case exposes a unit conflict and should not be selected as validated process performance.')
    figure = root / 'figures/02_sensitivity.png'
    if figure.exists():
        from PIL import Image as PILImage
        with PILImage.open(figure) as pic:
            width, height = pic.size
        story.append(Image(str(figure), width=510, height=510 * height / width))
    para('Cost uncertainty remains material. The most valuable next inputs are vendor quotes for DAC, electrolysis and process equipment, '
         'a reconciled Aspen heat/mass balance, and actual coproduct offtake terms.')

    story.append(PageBreak())
    para('Model checks and assumptions', 'Title')
    para(f'The base LP contains {result["variables"]:,} variables and {result["constraints"]:,} constraints. '
         f'HiGHS returned optimal status in {result["solve_seconds"]:.1f} seconds. '
         f'The maximum checked constraint violation is {max(result["validation"]["max_violations"].values()):.2e} in internal MW/MWh/tonne units.', 'Deck')
    para('Corrections implemented', 'Heading2')
    for text in [
        'UTC weather timestamps, checked against NSRDB solar geometry; explicit AC output per DC nameplate.',
        'All auxiliary heat draws electricity and has installed heater capacity; FT heat serves low-temperature DAC only.',
        'Corrected stated DAC capital units; consistent heat units and explicit uncertainty cases.',
        'Exact production target, cyclic storage, finite gas-storage flows, battery losses/duration, and cyclic fuel-train ramp limits.',
        'Bounded coproduct sales, replacement/consumable allowances, zero automatic removal credits, and additive cost exports.'
    ]:
        para('- ' + text)
    para('Economic convention and limitations', 'Heading2')
    para(f'Historical capital/O&amp;M benchmarks are escalated at an assumed {config["finance"]["annual_price_escalation_assumption"]:.0%}/year '
         f'to the analysis year, followed by constant real cash flows, a {config["finance"]["real_discount_rate"]:.0%} real discount rate '
         f'and a {config["finance"]["project_years"]}-year life. These are screening choices, not measured inflation or current supplier quotations. '
         'EIA observations are short-term fossil-product proxies, not a long-term SAF-price forecast.')
    para('The LP optimum is conditional on linear installed costs, fixed surrogate process coefficients, continuous operation and one historical weather year with perfect foresight. '
         'It does not certify an Aspen process simulation, lifecycle credit eligibility, fuel specification, plant availability, financing structure or delivered SAF price.')
    para('Primary references and reproducibility', 'Heading2')
    for title, url in [
        ('EIA dated petroleum spot-price observations', 'https://www.eia.gov/dnav/pet/PET_PRI_SPT_S1_D.htm'),
        ('DOE 2025 Q1 PV cost benchmarks', 'https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks'),
        ('DOE 2024 installed PEM estimate', 'https://www.energy.gov/sites/default/files/2024-05/hfto-mypp-2024.pdf'),
        ('IRS carbon-utilization eligibility instructions', 'https://www.irs.gov/instructions/i8933')
    ]:
        para(f'<link href="{url}" color="#246b80">{title}</link>', 'SmallNote')
    para('See model_assumptions_used.json and market_prices_used.json for inputs and source statuses; optimization_summary.json for recorded versions/hashes and solver checks; '
         'hourly_dispatch.csv for hourly states; docs/model_equations.md for equations; docs/model_audit.md for review findings. '
         'docs/file_relocations.json maps original run paths to the reorganized project files.', 'SmallNote')

    filename = root / 'solar_saf_final_report.pdf'
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#667780'))
        canvas.drawString(51, 25, f'Solar to Sustainable Aviation Fuel | {result["as_of"]} | Engineering screening estimate')
        canvas.drawRightString(561, 25, str(doc.page))
    SimpleDocTemplate(str(filename), pagesize=letter, rightMargin=51, leftMargin=51,
                      topMargin=40, bottomMargin=45, title='Final Solar-to-SAF Cost Model').build(story, onFirstPage=footer, onLaterPages=footer)
    print(f'PDF saved: {filename}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    build_report(parser.parse_args().run_directory)
