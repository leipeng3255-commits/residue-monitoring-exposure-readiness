"""Post hoc full-cutpoint diagnostic for PDP THPI reporting events.

This creates a new v36 output directory. It never writes to raw data or v35.
Run `--run` once, followed by `--verify` once.
"""

from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import argparse
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
CFG = {k: json.loads(v.strip()) for k, v in (
    line.split(':', 1) for line in (ROOT / '00_admin/paths.yaml').read_text().splitlines()
    if re.match(r'^[a-z_]+:\s*"', line)
)}
assert Path(CFG['project_root']).resolve() == ROOT
RAW = Path(CFG['raw_data_root'])
OUT = Path(CFG['outputs_root']) / 'manuscript_grilling_v36/pdp_threshold'
V35 = Path(CFG['outputs_root']) / 'manuscript_source_stability_v35/pdp'
PROTOCOL = ROOT / '01_protocol/pdp_full_cutpoint_sensitivity_v36.md'
MANIFEST = ROOT / '00_admin/download_manifest.csv'
YEARS = (2022, 2023)
CODE = '624'
COMMODITY = 'TO'
TYPE = 'FR'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n')


def write_csv(path, rows, fields=None):
    rows = list(rows)
    assert rows or fields
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def check_paths():
    result = subprocess.run(
        [sys.executable, str(ROOT / '05_code/utilities/check_paths.py')],
        cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0 and 'PASS overall' in result.stdout, result.stdout + result.stderr
    return result.stdout


def source_metadata(path, manifest):
    digest = sha(path)
    matches = [r for r in manifest if r['local_file_path'] == str(path)
               and r['sha256'] == digest and int(r['bytes']) == path.stat().st_size]
    assert matches, f'Archive not matched by manifest: {path}'
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest,
                official_url=matches[0]['official_url'],
                original_filename=matches[0]['original_filename'])


def direction(delta):
    return 'increase' if delta > 0 else 'decrease' if delta < 0 else 'zero'


def fmt_decimal(value):
    value = Decimal(value)
    text = format(value, 'f').rstrip('0').rstrip('.')
    return text or '0'


def read_primary(manifest):
    data, sources = {}, []
    for year in YEARS:
        archive = RAW / 'usda_pdp' / f'{year}PDPDatabase.zip'
        sources.append(source_metadata(archive, manifest))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            sample_member = f'PDP{str(year)[2:]}Samples.txt'
            samples = list(csv.reader(io.TextIOWrapper(z.open(sample_member), encoding='utf-8-sig'), delimiter='|'))
            chosen = {r[0] for r in samples if r[6] == COMMODITY and r[12] == TYPE}
            rows, seen = [], set()
            result_member = f'PDP{str(year)[2:]}Results.txt'
            for line_no, row in enumerate(csv.reader(
                    io.TextIOWrapper(z.open(result_member), encoding='utf-8-sig'), delimiter='|'), 1):
                if (row[1], row[2], row[4]) != (COMMODITY, TYPE, CODE):
                    continue
                assert row[0] in chosen and row[0] not in seen
                seen.add(row[0])
                assert row[8] == 'M'
                assert row[13] in {'ND', 'O', 'R'}
                assert row[11] in {'', 'V', 'X'} and row[12] == ''
                lod = Decimal(row[7]); assert lod > 0
                concentration = Decimal(row[6]) if row[6].strip() else None
                if row[13] == 'ND':
                    assert concentration is None or concentration == 0
                else:
                    assert concentration is not None and concentration > 0
                rows.append(dict(line=line_no, sample=row[0], state=row[13],
                                 concentration=concentration, lod=lod,
                                 annotation=row[11], lab=row[3]))
        assert rows
        data[year] = dict(frame_n=len(chosen), rows=rows,
                          tested_n=len(rows),
                          detected=[r['concentration'] for r in rows if r['state'] in {'O', 'R'}],
                          lods=[r['lod'] for r in rows])
    return data, sources


def event_row(label, cutpoint, data, observed_breakpoint=False, marker=''):
    counts = {}
    for year in YEARS:
        counts[year] = sum(x > cutpoint for x in data[year]['detected'])
    n1, n2 = data[2022]['tested_n'], data[2023]['tested_n']
    k1, k2 = counts[2022], counts[2023]
    p1, p2 = k1 / n1, k2 / n2
    delta = p2 - p1
    return dict(
        cutpoint_ppm=fmt_decimal(cutpoint), event_definition=label,
        observed_positive_breakpoint=observed_breakpoint, marker=marker,
        numerator_2022=k1, denominator_2022=n1, rate_2022_pct=100 * p1,
        numerator_2023=k2, denominator_2023=n2, rate_2023_pct=100 * p2,
        delta_2023_minus_2022_pp=100 * delta,
        point_estimate_direction=direction(delta),
        removed_from_native_2022=len(data[2022]['detected']) - k1,
        removed_from_native_2023=len(data[2023]['detected']) - k2,
    )


def native_row(data):
    k1, k2 = len(data[2022]['detected']), len(data[2023]['detected'])
    n1, n2 = data[2022]['tested_n'], data[2023]['tested_n']
    p1, p2 = k1 / n1, k2 / n2
    delta = p2 - p1
    return dict(
        event_definition='Source mean-result state O or R (native reporting event)',
        numerator_2022=k1, denominator_2022=n1, rate_2022_pct=100 * p1,
        numerator_2023=k2, denominator_2023=n2, rate_2023_pct=100 * p2,
        delta_2023_minus_2022_pp=100 * delta,
        point_estimate_direction=direction(delta),
    )


def make_intervals(data, positive_values, t_value):
    boundaries = [Decimal('0')] + positive_values
    atomic = []
    for i, lower in enumerate(boundaries):
        upper = boundaries[i + 1] if i + 1 < len(boundaries) else None
        row = event_row('O/R and concentration > lower endpoint', lower, data,
                        observed_breakpoint=lower in positive_values)
        atomic.append(dict(
            lower_inclusive_ppm=fmt_decimal(lower),
            upper_exclusive_ppm=fmt_decimal(upper) if upper is not None else 'infinity',
            numerator_2022=row['numerator_2022'], denominator_2022=row['denominator_2022'],
            numerator_2023=row['numerator_2023'], denominator_2023=row['denominator_2023'],
            delta_2023_minus_2022_pp=row['delta_2023_minus_2022_pp'],
            point_estimate_direction=row['point_estimate_direction'],
            contains_T=(lower <= t_value and (upper is None or t_value < upper)),
            contains_2T=(lower <= 2 * t_value and (upper is None or 2 * t_value < upper)),
        ))
    regions = []
    for row in atomic:
        if regions and regions[-1]['point_estimate_direction'] == row['point_estimate_direction']:
            regions[-1]['upper_exclusive_ppm'] = row['upper_exclusive_ppm']
            regions[-1]['atomic_intervals'] += 1
            regions[-1]['contains_T'] = regions[-1]['contains_T'] or row['contains_T']
            regions[-1]['contains_2T'] = regions[-1]['contains_2T'] or row['contains_2T']
        else:
            regions.append(dict(
                lower_inclusive_ppm=row['lower_inclusive_ppm'],
                upper_exclusive_ppm=row['upper_exclusive_ppm'],
                point_estimate_direction=row['point_estimate_direction'],
                atomic_intervals=1, contains_T=row['contains_T'], contains_2T=row['contains_2T']))
    return atomic, regions


def make_svg(profile, native, t_value, path):
    width, height = 1040, 700
    left, right, top, bottom = 120, 35, 85, 115
    plot_w, plot_h = width - left - right, height - top - bottom
    xmax = max(Decimal(r['cutpoint_ppm']) for r in profile) * Decimal('1.08')
    values = [float(r['delta_2023_minus_2022_pp']) for r in profile]
    ymin = math.floor((min(values) - 0.25) * 2) / 2
    ymax = math.ceil((max(values) + 0.25) * 2) / 2
    def x(v): return left + float(Decimal(v) / xmax) * plot_w
    def y(v): return top + (ymax - float(v)) / (ymax - ymin) * plot_h
    # Step coordinates: profile already includes all observed boundaries and markers.
    base = [r for r in profile if Decimal(r['cutpoint_ppm']) == 0 or r['observed_positive_breakpoint']]
    base.sort(key=lambda r: Decimal(r['cutpoint_ppm']))
    step_points = []
    for i, row in enumerate(base):
        xx = x(row['cutpoint_ppm']); yy = y(row['delta_2023_minus_2022_pp'])
        if i == 0:
            step_points.append((xx, yy))
        else:
            step_points.extend([(xx, step_points[-1][1]), (xx, yy)])
    step_points.append((x(xmax), step_points[-1][1]))
    path_d = ' '.join(('M' if i == 0 else 'L') + f'{px:.2f},{py:.2f}' for i, (px, py) in enumerate(step_points))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<metadata>Editable vector diagnostic generated by pdp_full_cutpoint_sensitivity_v36.py; post hoc, no exposure estimate.</metadata>',
           f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
           '<g font-family="Arial, Helvetica, sans-serif" fill="#17202a">',
           '<text x="25" y="38" font-size="30" font-weight="700">D</text>',
           '<text x="75" y="38" font-size="22" font-weight="700">THPI reporting direction depends on the concentration event</text>',
           '<text x="75" y="66" font-size="14" fill="#566573">Tomato PDP rows; 2023 minus 2022; unequal, partial code coverage retained</text>']
    # axes and horizontal grid
    ticks_y = [ymin + 0.5 * i for i in range(int(round((ymax - ymin) / 0.5)) + 1)]
    for tick in ticks_y:
        yy = y(tick)
        color = '#aeb6bf' if tick == 0 else '#e8ecef'
        stroke = 1.6 if tick == 0 else 1
        out.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{width-right}" y2="{yy:.2f}" stroke="{color}" stroke-width="{stroke}"/>')
        label = f'{tick:.1f}'.rstrip('0').rstrip('.')
        out.append(f'<text x="{left-15}" y="{yy+5:.2f}" text-anchor="end" font-size="13">{label}</text>')
    for tick in [Decimal('0'), Decimal('0.02'), Decimal('0.04'), Decimal('0.06'), Decimal('0.08')]:
        if tick <= xmax:
            xx = x(tick)
            out.append(f'<line x1="{xx:.2f}" y1="{height-bottom}" x2="{xx:.2f}" y2="{height-bottom+6}" stroke="#566573"/>')
            out.append(f'<text x="{xx:.2f}" y="{height-bottom+27}" text-anchor="middle" font-size="13">{float(tick):.2f}</text>')
    out.append(f'<path d="{path_d}" fill="none" stroke="#1f618d" stroke-width="3.2" stroke-linejoin="miter"/>')
    # observed breakpoints
    for row in base:
        xx, yy = x(row['cutpoint_ppm']), y(row['delta_2023_minus_2022_pp'])
        out.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="4.2" fill="#1f618d" stroke="#ffffff" stroke-width="1.2"/>')
    # T / 2T reference markers
    marker_styles = [('T', t_value, '#d35400'), ('2T', 2 * t_value, '#7d3c98')]
    profile_map = {Decimal(r['cutpoint_ppm']): r for r in profile}
    for label, cut, color in marker_styles:
        row = profile_map[cut]; xx, yy = x(cut), y(row['delta_2023_minus_2022_pp'])
        out.append(f'<line x1="{xx:.2f}" y1="{top}" x2="{xx:.2f}" y2="{height-bottom}" stroke="{color}" stroke-width="1.7" stroke-dasharray="7 6"/>')
        out.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="6" fill="{color}" stroke="#ffffff" stroke-width="1.4"/>')
        out.append(f'<text x="{xx+8:.2f}" y="{top+18 if label == "T" else top+40}" font-size="14" font-weight="700" fill="{color}">{label}={fmt_decimal(cut)} ppm</text>')
    out.extend([
        f'<text x="{left + plot_w/2:.2f}" y="{height-50}" text-anchor="middle" font-size="16">Cutpoint c (ppm); event = O/R concentration &gt; c</text>',
        f'<text x="28" y="{top + plot_h/2:.2f}" text-anchor="middle" font-size="16" transform="rotate(-90 28 {top + plot_h/2:.2f})">2023 − 2022 difference (percentage points)</text>',
        f'<rect x="{width-right-330}" y="{top+380}" width="320" height="68" rx="5" fill="#f8f9f9" stroke="#d5d8dc"/>',
        f'<text x="{width-right-316}" y="{top+404}" font-size="14" font-weight="700">Native O/R: {native["delta_2023_minus_2022_pp"]:.2f} pp</text>',
        f'<text x="{width-right-316}" y="{top+425}" font-size="13">2022: {native["numerator_2022"]}/{native["denominator_2022"]}; 2023: {native["numerator_2023"]}/{native["denominator_2023"]}</text>',
        f'<text x="{width-right-316}" y="{top+443}" font-size="12" fill="#566573">Exact source-row arithmetic</text>',
        f'<text x="{left}" y="{height-18}" font-size="11" fill="#566573">Post hoc event diagnostic; point-estimate direction only—not a national contamination, exposure, risk or health trend.</text>',
        '</g></svg>'])
    path.write_text('\n'.join(out) + '\n')


def run():
    paths = check_paths()
    assert not OUT.exists(), f'Refuse to replace existing output directory: {OUT}'
    OUT.mkdir(parents=True)
    (OUT / 'path_check_at_run.txt').write_text(paths)
    manifest_bytes = MANIFEST.read_bytes()
    manifest = list(csv.DictReader(io.StringIO(manifest_bytes.decode('utf-8-sig'))))
    data, sources = read_primary(manifest)
    dispositions = {r['code']: r for r in csv.DictReader((V35 / 'all_common_code_dispositions.csv').open())}
    assert dispositions[CODE]['disposition'] == 'ELIGIBLE_SOURCE_CONDITIONAL'
    assert dispositions[CODE]['risk_residue_definition'] == 'NOT_CERTIFIED'
    assert [data[y]['tested_n'] for y in YEARS] == [226, 314]
    assert [len(data[y]['detected']) for y in YEARS] == [6, 4]
    t_value = max(max(data[y]['lods']) for y in YEARS)
    assert t_value == Decimal('0.024')
    positive_values = sorted(set(x for y in YEARS for x in data[y]['detected']))
    cutpoints = sorted(set([Decimal('0'), t_value, 2 * t_value] + positive_values))
    profile = []
    for cut in cutpoints:
        markers = []
        if cut == t_value: markers.append('T')
        if cut == 2 * t_value: markers.append('2T')
        profile.append(event_row('Source state O/R and reported concentration > cutpoint', cut, data,
                                 observed_breakpoint=cut in positive_values,
                                 marker=';'.join(markers)))
    native = native_row(data)
    atomic, regions = make_intervals(data, positive_values, t_value)
    write_csv(OUT / 'native_reporting_event.csv', [native])
    write_csv(OUT / 'cutpoint_profile.csv', profile)
    write_csv(OUT / 'atomic_cutpoint_intervals.csv', atomic)
    write_csv(OUT / 'direction_regions.csv', regions)
    positive_rows = []
    for year in YEARS:
        for row in data[year]['rows']:
            if row['state'] in {'O', 'R'}:
                positive_rows.append(dict(year=year, source_line_1based=row['line'], sample_pk=row['sample'],
                                          mean_state=row['state'], concentration_ppm=fmt_decimal(row['concentration']),
                                          lod_ppm=fmt_decimal(row['lod']), annotation=row['annotation'], lab=row['lab']))
    write_csv(OUT / 'positive_source_rows.csv', positive_rows)
    dump(OUT / 'source_provenance.json', sources)
    make_svg(profile, native, t_value, OUT / 'figure_4D_full_cutpoint_sensitivity.svg')
    region_label = lambda r: f"[{r['lower_inclusive_ppm']}, {r['upper_exclusive_ppm']})"
    summary = dict(
        status='COMPLETED_POST_HOC_REPORTING_EVENT_DIAGNOSTIC',
        completed_utc=datetime.now(timezone.utc).isoformat(),
        protocol_path=str(PROTOCOL), protocol_sha256=sha(PROTOCOL),
        script_sha256=sha(Path(__file__)), manifest_snapshot_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        code=CODE, source_label='Tetrahydrophthalimide (THPI)', commodity=COMMODITY, type=TYPE,
        frame_n={str(y): data[y]['frame_n'] for y in YEARS},
        tested_denominators={str(y): data[y]['tested_n'] for y in YEARS},
        native_event=native, pooled_max_lod_T_ppm=fmt_decimal(t_value), two_T_ppm=fmt_decimal(2 * t_value),
        distinct_positive_breakpoints_ppm=[fmt_decimal(v) for v in positive_values],
        evaluated_numeric_cutpoints=len(profile),
        point_estimate_direction_regions=[dict(**r, interval=region_label(r)) for r in regions],
        T_result=next(r for r in profile if Decimal(r['cutpoint_ppm']) == t_value),
        two_T_result=next(r for r in profile if Decimal(r['cutpoint_ppm']) == 2 * t_value),
        key_interpretation=(
            'The point estimate decreases for 0 <= c < 0.021 ppm, increases for '
            '0.021 <= c < 0.089 ppm, and is zero at c >= 0.089 ppm. T and 2T both lie '
            'inside the increase region.'),
        sampling_uncertainty=(
            'No sampling confidence interval or p value is reported: code-specific tested subsets '
            'have partial, unequal coverage and no established probability-sampling design for this comparison.'),
        inference_limits=(
            'Post hoc selected-code reporting-event diagnostic with unequal partial coverage. '
            'No national contamination trend, exposure estimate, risk estimate, health effect, '
            'or certified risk-assessment residue definition.'),
        new_exposure_estimates=0, p_values=0, downloads=0, raw_files_modified=0,
        independent_human_validation='NOT_PERFORMED')
    dump(OUT / 'summary.json', summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def verify():
    """Separate parser and exact rational count/difference verification."""
    check_paths()
    receipt_path = OUT / 'independent_arithmetic_verification.json'
    assert OUT.is_dir() and not receipt_path.exists()
    summary = json.loads((OUT / 'summary.json').read_text())
    profile = list(csv.DictReader((OUT / 'cutpoint_profile.csv').open()))
    direct = {}
    sources = json.loads((OUT / 'source_provenance.json').read_text())
    for year in YEARS:
        archive = RAW / 'usda_pdp' / f'{year}PDPDatabase.zip'
        with zipfile.ZipFile(archive) as z:
            sample_lines = z.read(f'PDP{str(year)[2:]}Samples.txt').decode('utf-8-sig').splitlines()
            chosen = {r[0] for r in (line.split('|') for line in sample_lines)
                      if r[6] == COMMODITY and r[12] == TYPE}
            records = []
            for binary in z.open(f'PDP{str(year)[2:]}Results.txt'):
                r = binary.decode('utf-8-sig').rstrip('\r\n').split('|')
                if (r[1], r[2], r[4]) != (COMMODITY, TYPE, CODE):
                    continue
                assert r[0] in chosen
                records.append(r)
            assert len({r[0] for r in records}) == len(records)
            positives = [Fraction(r[6]) for r in records if r[13] in {'O', 'R'}]
            lods = [Fraction(r[7]) for r in records]
            direct[year] = dict(n=len(records), positives=positives, max_lod=max(lods))
    assert direct[2022]['n'] == 226 and direct[2023]['n'] == 314
    assert [len(direct[y]['positives']) for y in YEARS] == [6, 4]
    assert max(direct[y]['max_lod'] for y in YEARS) == Fraction(3, 125)  # 0.024
    checks = []
    for row in profile:
        cut = Fraction(row['cutpoint_ppm'])
        nums = {y: sum(v > cut for v in direct[y]['positives']) for y in YEARS}
        assert nums[2022] == int(row['numerator_2022'])
        assert nums[2023] == int(row['numerator_2023'])
        exact_delta_pp = (Fraction(nums[2023], direct[2023]['n']) -
                          Fraction(nums[2022], direct[2022]['n'])) * 100
        assert abs(float(exact_delta_pp) - float(row['delta_2023_minus_2022_pp'])) < 1e-12
        assert direction(exact_delta_pp) == row['point_estimate_direction']
        checks.append(dict(cutpoint_ppm=row['cutpoint_ppm'], numerator_2022=nums[2022],
                           numerator_2023=nums[2023], exact_delta_pp=str(exact_delta_pp), pass_check=True))
    # Verify expected maximal direction regions from exact arithmetic over observed boundaries.
    exact_regions = []
    for row in list(csv.DictReader((OUT / 'direction_regions.csv').open())):
        exact_regions.append((row['lower_inclusive_ppm'], row['upper_exclusive_ppm'], row['point_estimate_direction']))
    assert exact_regions == [('0', '0.021', 'decrease'), ('0.021', '0.089', 'increase'), ('0.089', 'infinity', 'zero')]
    for source in sources:
        assert sha(source['path']) == source['sha256']
    output_hashes = {p.name: sha(p) for p in sorted(OUT.iterdir())
                     if p.is_file() and p.name != receipt_path.name and not p.name.startswith('._')}
    receipt = dict(
        status='PASS', verified_utc=datetime.now(timezone.utc).isoformat(),
        checked_cutpoints=len(checks), checks=checks,
        exact_direction_regions=[dict(lower=a, upper_exclusive=b, direction=c) for a, b, c in exact_regions],
        source_sha256_rechecks=len(sources), protocol_sha256_recheck=sha(PROTOCOL),
        production_summary_sha256=sha(OUT / 'summary.json'), output_hashes=output_hashes,
        implementation=(
            'Direct binary line splitting, exact Fraction counts and differences, and independent '
            'region assertions; no calls to the '
            'production CSV parser, event-row, interval, or SVG functions.'),
        scope=(
            'Independent arithmetic implementation within the same AI-assisted project; not independent '
            'personnel, external adjudication, or scientific validation.'),
        raw_files_modified=0)
    dump(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', action='store_true')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    run() if args.run else verify()
