"""Bounded, protocol-locked PDP reporting-frame comparison; no exposure estimates.

Run with --lock, then --run, then --verify. All scientific data remain external.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import argparse
import csv
import hashlib
import io
import json
import re
import statistics
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CFG = {k: json.loads(v.strip()) for k, v in (line.split(':', 1) for line in
       (ROOT / '00_admin/paths.yaml').read_text().splitlines()
       if re.match(r'^[a-z_]+:\s*"', line))}
assert Path(CFG['project_root']).resolve() == ROOT
RAW = Path(CFG['raw_data_root'])
OUT = Path(CFG['outputs_root']) / 'manuscript_source_stability_v35/pdp'
PROTOCOL = ROOT / '01_protocol/pdp_temporal_comparability_v35.md'
YEARS = (2022, 2023)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n')


def write_csv(name, rows, fieldnames=None):
    assert rows or fieldnames
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def packed(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def num(value):
    try:
        x = Decimal(value)
        return x if x.is_finite() else None
    except (InvalidOperation, TypeError):
        return None


def sign(a, b):
    return (a > b) - (a < b)


def direction(n22, d22, n23, d23):
    return sign(n23 * d22, n22 * d23)


def transition(native, threshold):
    if native == threshold:
        return 'stable_zero' if native == 0 else 'stable_increase' if native > 0 else 'stable_decrease'
    if threshold == 0:
        return 'attenuated_to_zero'
    if native == 0:
        return 'emergence_from_zero'
    return 'reversal'


def freeze_check():
    rows = json.loads((ROOT / '00_admin/analysis_freeze_manifest_20260921.json').read_text())['files']
    assert len(rows) == 95
    for row in rows:
        assert sha(Path(row['path'])) == row['sha256'], row['path']
    return len(rows)


def check_paths():
    result = subprocess.run([sys.executable, str(ROOT / '05_code/utilities/check_paths.py')],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0 and 'PASS overall' in result.stdout, result.stdout + result.stderr
    return result.stdout


def lock():
    paths_check = check_paths()
    assert not OUT.exists(), f'Refuse to replace existing outputs: {OUT}'
    OUT.mkdir(parents=True)
    dump('protocol_lock.json', dict(locked_utc=datetime.now(timezone.utc).isoformat(),
        protocol_path=str(PROTOCOL), protocol_sha256=sha(PROTOCOL),
        script_sha256_at_lock=sha(Path(__file__)),
        directions_read_before_lock=False,
        knowledge='Retrospective feasibility audit and official dictionary/reference semantics known; no new direction comparisons read.'))
    (OUT / 'path_check_at_lock.txt').write_text(paths_check)
    print('Protocol locked:', sha(PROTOCOL), flush=True)


def source_docs(z, year):
    ref = f'PDP ReferenceTables {year}.pdf'
    doc = f'PDP DataDictionary {year}.pdf'
    members = {}
    for name in z.namelist():
        if name.endswith(('.pdf', '.xls')):
            members[name] = dict(bytes=z.getinfo(name).file_size,
                sha256=hashlib.sha256(z.read(name)).hexdigest())
    text = subprocess.run(['pdftotext', '-layout', '-', '-'], input=z.read(ref),
                          capture_output=True, check=True).stdout.decode()
    pages = text.split('\f')
    first = next(i for i, p in enumerate(pages) if 'Compounds (PESTICIDES)' in p)
    last = next(i for i, p in enumerate(pages) if 'QUANTITATION METHOD' in p)
    names = {}
    for page_idx, page in enumerate(pages[first:last], first + 1):
        for line in page.splitlines():
            match = re.match(r'^\s*(\S{3})\s+(.+?)\s{2,}([A-Z])\s+(\d+)\s*$', line)
            if match:
                assert match[1] not in names
                names[match[1]] = dict(name=match[2].strip(), test_class=match[3], page=page_idx)
            elif re.match(r'^\s*\d{3}\s', line):
                raise AssertionError(f'Unparsed reference line {year}: {line}')
    methods = {}
    extracts = []
    for title, key in [('EXTRACTION METHOD', 'extract'), ('DETERMINATIVE METHOD', 'determin'),
                       ('CONFIRMATION METHOD', 'confirm')]:
        page_idx, page = next((i, p) for i, p in enumerate(pages, 1) if title in p)
        mapping = {}
        for line in page.splitlines():
            match = re.match(r'^\s*([A-Z0-9]{2,3})\s{2,}(.+?)\s*$', line)
            if match:
                mapping[match[1]] = match[2].strip()
        assert mapping
        methods[key] = mapping
        extracts.append(dict(member=ref, page=page_idx, text=page))
    for i, page in enumerate(pages, 1):
        if any(k in page for k in ['ANNOTATED INFORMATION', 'MEAN RESULT', 'QUANTITATION METHOD']):
            extracts.append(dict(member=ref, page=i, text=page))
    dictionary = subprocess.run(['pdftotext', '-layout', '-', '-'], input=z.read(doc),
                          capture_output=True, check=True).stdout.decode()
    assert 'Limit of Detection' in dictionary and 'Concentration of residue detected' in dictionary
    return names, methods, dict(year=year, members=members, dictionary=dictionary,
                                reference_semantics=extracts, reference_methods=methods)


def source_metadata(path, manifest):
    digest = sha(path)
    rows = [r for r in manifest if r['local_file_path'] == str(path)
            and r['sha256'] == digest and int(r['bytes']) == path.stat().st_size]
    assert rows, f'Source not matched by manifest: {path}'
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest,
                official_url=rows[0]['official_url'], original_filename=rows[0]['original_filename'])


def run():
    check_paths()
    assert not (OUT / 'summary.json').exists(), 'Completed run is immutable; use a separately approved output version.'
    locked = json.loads((OUT / 'protocol_lock.json').read_text())
    assert locked['protocol_sha256'] == sha(PROTOCOL), 'Protocol changed after lock'
    freeze_before = freeze_check()
    manifest_bytes = (ROOT / '00_admin/download_manifest.csv').read_bytes()
    manifest = list(csv.DictReader(io.StringIO(manifest_bytes.decode('utf-8-sig'))))
    sources, docs, references, methods, samples, results = [], [], {}, {}, {}, {}
    for year in YEARS:
        path = RAW / 'usda_pdp' / f'{year}PDPDatabase.zip'
        sources.append(source_metadata(path, manifest))
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            references[year], methods[year], doc = source_docs(z, year)
            docs.append(doc)
            member = f'PDP{str(year)[2:]}Samples.txt'
            rows = list(csv.reader(io.TextIOWrapper(z.open(member), encoding='utf-8-sig'), delimiter='|'))
            assert all(len(row) == 18 for row in rows)
            assert len({r[0] for r in rows}) == len(rows)
            chosen = {row[0]: row for row in rows if row[6] == 'TO' and row[12] == 'FR'}
            assert len(chosen) == {2022: 709, 2023: 708}[year]
            samples[year] = chosen
            results[year] = defaultdict(list)
            seen = set()
            member = f'PDP{str(year)[2:]}Results.txt'
            for raw_line_no, row in enumerate(csv.reader(io.TextIOWrapper(z.open(member), encoding='utf-8-sig'), delimiter='|'), 1):
                assert len(row) == 16
                if (row[1], row[2]) != ('TO', 'FR'):
                    continue
                assert row[0] in chosen
                key = (row[0], row[4])
                assert key not in seen
                seen.add(key)
                results[year][row[4]].append((raw_line_no, row))
    codes = sorted(set(results[2022]) & set(results[2023]))
    assert len(codes) == 362
    dump('source_provenance.json', sources)
    dump('source_semantics.json', docs)
    write_csv('official_analyte_reference.csv', [dict(year=y, code=c, **v)
        for y in YEARS for c, v in sorted(references[y].items())])
    frame_rows = []
    for y in YEARS:
        for field, idx in [('month', 3), ('origin', 9), ('country', 10), ('claim', 13), ('collection_state', 1)]:
            for value, count in sorted(Counter(r[idx] for r in samples[y].values()).items()):
                frame_rows.append(dict(year=y, field=field, value=value, n=count, frame_n=len(samples[y])))
    write_csv('sample_frame_composition.csv', frame_rows)
    profiles, row_holds = {}, {}
    for y in YEARS:
        for code, records in sorted(results[y].items()):
            rows = [r for _, r in records]
            reasons = Counter()
            lods = []
            ref = references[y].get(code)
            for row in rows:
                lod = num(row[7]); conc = num(row[6])
                if lod is None or lod <= 0:
                    reasons['LOD_UNRESOLVED'] += 1
                else:
                    lods.append(lod)
                if row[8] != 'M': reasons['UNIT_NOT_M'] += 1
                if row[13] == 'NP': reasons['MARGINAL_NP'] += 1
                elif row[13] not in {'ND', 'O', 'R'}: reasons['MEAN_UNKNOWN'] += 1
                if row[11] in {'Q', 'QV'}: reasons['BQL_WITHOUT_NUMERIC_LOQ'] += 1
                elif row[11] not in {'', 'V', 'X'}: reasons['ANNOTATION_UNKNOWN'] += 1
                if row[12]: reasons['QUANTITATION_' + row[12]] += 1
                if row[13] == 'ND' and row[6].strip() and conc != 0:
                    reasons['ND_CONCENTRATION_CONFLICT'] += 1
                if row[13] in {'O', 'R'} and (conc is None or conc <= 0):
                    reasons['DETECT_CONCENTRATION_UNRESOLVED'] += 1
                if not ref or row[5] != ref['test_class']:
                    reasons['TESTCLASS_UNRESOLVED'] += 1
                for key, idx in [('extract', 14), ('determin', 15)]:
                    if row[idx] not in methods[y][key]: reasons[key.upper() + '_UNDOCUMENTED'] += 1
                for idx in (9, 10):
                    if row[idx] and row[idx] not in methods[y]['confirm']:
                        reasons['CONFIRM_UNDOCUMENTED'] += 1
                if row[14] == 'P90': reasons['EXTRACTION_P90'] += 1
            row_holds[y, code] = reasons
            profile = dict(year=y, code=code, name=ref['name'] if ref else '',
                tested_n=len(rows), frame_n=len(samples[y]), coverage_fraction=len(rows) / len(samples[y]),
                native_OR_n=sum(r[13] in {'O', 'R'} for r in rows),
                ND_n=sum(r[13] == 'ND' for r in rows), NP_n=sum(r[13] == 'NP' for r in rows),
                Q_QV_n=sum(r[11] in {'Q', 'QV'} for r in rows),
                E_n=sum(r[12] == 'E' for r in rows), P_n=sum(r[12] == 'P' for r in rows),
                lod_min=str(min(lods)) if lods else '',
                lod_median=str(statistics.median(lods)) if lods else '',
                lod_max=str(max(lods)) if lods else '',
                units=packed(Counter(r[8] for r in rows)),
                mean_states=packed(Counter(r[13] for r in rows)),
                annotations=packed(Counter(r[11] for r in rows)),
                quantitation=packed(Counter(r[12] for r in rows)),
                extraction=packed(Counter(r[14] for r in rows)),
                determination=packed(Counter(r[15] for r in rows)),
                confirmation_primary=packed(Counter(r[9] for r in rows)),
                confirmation_secondary=packed(Counter(r[10] for r in rows)),
                laboratories=packed(Counter(r[3] for r in rows)),
                months=packed(Counter(samples[y][r[0]][3] for r in rows)),
                origins=packed(Counter(samples[y][r[0]][9] for r in rows)),
                claims=packed(Counter(samples[y][r[0]][13] for r in rows)),
                row_hold_reasons=packed(reasons))
            profiles[y, code] = profile
    write_csv('all_analyte_year_profiles.csv', list(profiles.values()))
    audit, comparisons = [], []
    for code in codes:
        a, b = profiles[2022, code], profiles[2023, code]
        r22, r23 = references[2022].get(code), references[2023].get(code)
        reasons = set(row_holds[2022, code]) | set(row_holds[2023, code])
        pair = (a['name'], b['name'])
        permitted = {'083': ('O-Phenylphenol', 'o-Phenylphenol'),
                     '587': ('Pirimiphos-ethyl', 'Pirimiphos ethyl')}
        label_state = 'EXACT_SOURCE_LABEL'
        if not r22 or not r23:
            label_state = 'MISSING'; reasons.add('LABEL_MISSING')
        elif pair[0] != pair[1]:
            if permitted.get(code) == pair:
                label_state = 'DOCUMENTED_TYPOGRAPHIC_PAIR'
            else:
                label_state = 'UNRESOLVED'; reasons.add('LABEL_MISMATCH')
        if r22 and r23 and r22['test_class'] != r23['test_class']:
            reasons.add('TESTCLASS_CHANGED')
        for key, column in [('extract', 'extraction'), ('determin', 'determination')]:
            set22, set23 = set(json.loads(a[column])), set(json.loads(b[column]))
            if set22 != set23:
                reasons.add(key.upper() + '_METHOD_SET_CHANGED')
            for method in set22 & set23:
                if methods[2022][key].get(method) != methods[2023][key].get(method):
                    reasons.add(key.upper() + '_DESCRIPTION_CHANGED')
        combined = dict(code=code, name_2022=a['name'], name_2023=b['name'],
            label_correspondence=label_state, risk_residue_definition='NOT_CERTIFIED',
            disposition='HOLD' if reasons else 'ELIGIBLE_SOURCE_CONDITIONAL',
            hold_reasons=';'.join(sorted(reasons)),
            hold_reason_count=len(reasons), tested_2022=a['tested_n'], tested_2023=b['tested_n'],
            frame_2022=a['frame_n'], frame_2023=b['frame_n'],
            coverage_2022=a['coverage_fraction'], coverage_2023=b['coverage_fraction'],
            full_coverage_both=a['tested_n'] == 709 and b['tested_n'] == 708,
            NP_2022=a['NP_n'], NP_2023=b['NP_n'], Q_QV_2022=a['Q_QV_n'], Q_QV_2023=b['Q_QV_n'],
            E_2022=a['E_n'], E_2023=b['E_n'], P_2022=a['P_n'], P_2023=b['P_n'],
            native_OR_2022=a['native_OR_n'], native_OR_2023=b['native_OR_n'],
            lod_median_2022=a['lod_median'], lod_median_2023=b['lod_median'],
            lod_max_2022=a['lod_max'], lod_max_2023=b['lod_max'],
            extraction_2022=a['extraction'], extraction_2023=b['extraction'],
            determination_2022=a['determination'], determination_2023=b['determination'],
            laboratories_2022=a['laboratories'], laboratories_2023=b['laboratories'])
        audit.append(combined)
        if reasons:
            continue
        threshold = max(Decimal(a['lod_max']), Decimal(b['lod_max']))
        n1, n2 = a['native_OR_n'], b['native_OR_n']
        d1, d2 = a['tested_n'], b['tested_n']
        native_dir = direction(n1, d1, n2, d2)
        for multiplier in (1, 2):
            cutoff = threshold * multiplier
            numer = {y: sum(r[13] in {'O', 'R'} and Decimal(r[6]) > cutoff
                              for _, r in results[y][code]) for y in YEARS}
            threshold_dir = direction(numer[2022], d1, numer[2023], d2)
            comparisons.append(dict(code=code, name=a['name'],
                threshold_multiplier=multiplier, threshold_ppm=str(cutoff),
                native_numerator_2022=n1, native_denominator_2022=d1,
                native_numerator_2023=n2, native_denominator_2023=d2,
                threshold_numerator_2022=numer[2022], threshold_denominator_2022=d1,
                threshold_numerator_2023=numer[2023], threshold_denominator_2023=d2,
                native_fraction_2022=n1 / d1, native_fraction_2023=n2 / d2,
                threshold_fraction_2022=numer[2022] / d1,
                threshold_fraction_2023=numer[2023] / d2,
                native_delta_pp=100 * (n2 / d2 - n1 / d1),
                threshold_delta_pp=100 * (numer[2023] / d2 - numer[2022] / d1),
                native_direction=native_dir, threshold_direction=threshold_dir,
                direction_comparison=transition(native_dir, threshold_dir),
                full_coverage_both=combined['full_coverage_both'],
                removed_detects_2022=n1 - numer[2022], removed_detects_2023=n2 - numer[2023]))
    write_csv('all_common_code_dispositions.csv', audit)
    fields = ['code', 'name', 'threshold_multiplier', 'threshold_ppm', 'native_numerator_2022',
        'native_denominator_2022', 'native_numerator_2023', 'native_denominator_2023',
        'threshold_numerator_2022', 'threshold_denominator_2022', 'threshold_numerator_2023',
        'threshold_denominator_2023', 'native_fraction_2022', 'native_fraction_2023',
        'threshold_fraction_2022', 'threshold_fraction_2023', 'native_delta_pp',
        'threshold_delta_pp', 'native_direction', 'threshold_direction', 'direction_comparison',
        'full_coverage_both', 'removed_detects_2022', 'removed_detects_2023']
    write_csv('eligible_comparisons.csv', comparisons, fields)
    hold_counts = Counter(reason for row in audit for reason in row['hold_reasons'].split(';') if reason)
    primary = [r for r in comparisons if r['threshold_multiplier'] == 1]
    sensitivity = [r for r in comparisons if r['threshold_multiplier'] == 2]
    for s in sources:
        assert sha(Path(s['path'])) == s['sha256']
    freeze_after = freeze_check()
    summary = dict(status='COMPLETED_SOURCE_CONDITIONAL_DESCRIPTIVE_ANALYSIS',
        protocol_lock=locked, protocol_sha256=sha(PROTOCOL), script_sha256=sha(Path(__file__)),
        finished_utc=datetime.now(timezone.utc).isoformat(),
        manifest_snapshot_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        frames={y: len(samples[y]) for y in YEARS},
        result_rows={y: sum(len(v) for v in results[y].values()) for y in YEARS},
        all_codes={y: len(results[y]) for y in YEARS}, common_codes=len(codes),
        only_codes={y: sorted(set(results[y]) - set(codes)) for y in YEARS},
        source_label_dispositions=dict(Counter(r['label_correspondence'] for r in audit)),
        eligible_codes=len(primary), held_codes=len(audit) - len(primary),
        overlapping_hold_reason_code_counts=dict(hold_counts),
        primary_direction_counts=dict(Counter(r['direction_comparison'] for r in primary)),
        sensitivity_2T_direction_counts=dict(Counter(r['direction_comparison'] for r in sensitivity)),
        eligible_full_coverage_codes=sum(r['full_coverage_both'] for r in primary),
        eligible_partial_coverage_codes=sum(not r['full_coverage_both'] for r in primary),
        common_partial_coverage_codes=sum(not r['full_coverage_both'] for r in audit),
        common_changed_median_lod=sum(r['lod_median_2022'] != r['lod_median_2023'] for r in audit),
        common_changed_max_lod=sum(r['lod_max_2022'] != r['lod_max_2023'] for r in audit),
        eligible_primary_has_any_native_detection=sum(r['native_numerator_2022'] + r['native_numerator_2023'] > 0 for r in primary),
        eligible_2022_tested_range=[min((r['native_denominator_2022'] for r in primary), default=0), max((r['native_denominator_2022'] for r in primary), default=0)],
        eligible_2023_tested_range=[min((r['native_denominator_2023'] for r in primary), default=0), max((r['native_denominator_2023'] for r in primary), default=0)],
        source_rehash_pass=2, zip_crc_pass=2, parent_freeze_before=freeze_before,
        parent_freeze_after=freeze_after, new_exposure_estimates=0, downloads=0,
        independent_human_validation='NOT_PERFORMED', author_approval='PENDING',
        limits='HOLD is protocol-specific, not invalidation of official results. All eligible outcomes are source-conditional reporting observations, not true concentrations, national trends, risk, or health effects.')
    dump('summary.json', summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def verify():
    """Second implementation: direct text splitting, Fraction arithmetic and pypdf."""
    from pypdf import PdfReader
    check_paths()
    assert not (OUT / 'separate_arithmetic_verification.json').exists(), 'Verification receipt already exists'
    summary = json.loads((OUT / 'summary.json').read_text())
    dispositions = list(csv.DictReader((OUT / 'all_common_code_dispositions.csv').open()))
    expected = list(csv.DictReader((OUT / 'eligible_comparisons.csv').open()))
    eligible = {r['code'] for r in dispositions if r['disposition'] == 'ELIGIBLE_SOURCE_CONDITIONAL'}
    counters = {}; all_seen = {}; code_names = {}
    reference_rows = list(csv.DictReader((OUT / 'official_analyte_reference.csv').open()))
    checks = []
    for y in YEARS:
        with zipfile.ZipFile(RAW / 'usda_pdp' / f'{y}PDPDatabase.zip') as z:
            # Deliberately different table reader, PDF renderer, counters and arithmetic.
            ref = PdfReader(io.BytesIO(z.read(f'PDP ReferenceTables {y}.pdf')))
            parsed = {}
            for p in ref.pages:
                page = p.extract_text()
                for line in page.splitlines():
                    m = re.match(r'^\s*([A-Z0-9]{3})\s+(.+?)\s+([A-Z])\s+(\d+)\s*$', line)
                    if m:
                        assert m[1] not in parsed
                        # PDF text renderers insert differing interword spacing.
                        # This normalization is within-file reader verification,
                        # not the cross-year chemical-label equivalence gate.
                        parsed[m[1]] = (' '.join(m[2].split()), m[3])
            for record in reference_rows:
                if int(record['year']) == y:
                    assert parsed[record['code']] == (record['name'], record['test_class']), record
            code_names[y] = len(parsed)
            sample_lines = z.read(f'PDP{str(y)[2:]}Samples.txt').decode('utf-8-sig').splitlines()
            chosen = {r[0] for r in (line.split('|') for line in sample_lines) if r[6] == 'TO' and r[12] == 'FR'}
            assert len(chosen) == summary['frames'][str(y)]
            all_seen[y] = set()
            with z.open(f'PDP{str(y)[2:]}Results.txt') as stream:
                for binary in stream:
                    r = binary.decode('utf-8-sig').rstrip('\r\n').split('|')
                    if r[1] != 'TO' or r[2] != 'FR': continue
                    assert r[0] in chosen
                    all_seen[y].add(r[4])
                    key = (y, r[4])
                    if key not in counters:
                        counters[key] = dict(ids=set(), n=0, detected=0, max_lod=Fraction(0),
                                             concentrations=[], holds=Counter())
                    v = counters[key]
                    assert r[0] not in v['ids']; v['ids'].add(r[0]); v['n'] += 1
                    if r[13] == 'NP': v['holds']['NP'] += 1
                    if r[11] in ('Q', 'QV'): v['holds']['BQL'] += 1
                    if r[12]: v['holds']['quantitation'] += 1
                    if r[4] not in eligible: continue
                    assert r[13] in ('ND', 'O', 'R') and r[11] in ('', 'V', 'X') and r[12] == ''
                    assert r[8] == 'M'
                    bound = Fraction(r[7]); assert bound > 0
                    v['max_lod'] = max(bound, v['max_lod'])
                    if r[13] == 'ND':
                        assert r[6] == '' or Fraction(r[6]) == 0
                    else:
                        value = Fraction(r[6]); assert value > 0
                        v['detected'] += 1; v['concentrations'].append(value)
    assert len(all_seen[2022] & all_seen[2023]) == 362
    assert {r['code'] for r in dispositions} == all_seen[2022] & all_seen[2023]
    for row in dispositions:
        for y in YEARS:
            v = counters[y, row['code']]
            assert v['n'] == int(row[f'tested_{y}'])
            assert v['holds']['NP'] == int(row[f'NP_{y}'])
            assert v['holds']['BQL'] == int(row[f'Q_QV_{y}'])
            if v['holds']:
                assert row['disposition'] == 'HOLD'
    for row in expected:
        code = row['code']; multiplier = int(row['threshold_multiplier'])
        v1, v2 = counters[2022, code], counters[2023, code]
        cutoff = max(v1['max_lod'], v2['max_lod']) * multiplier
        assert cutoff == Fraction(row['threshold_ppm'])
        native_rates, threshold_rates = [], []
        for y, v in ((2022, v1), (2023, v2)):
            numerator = len([x for x in v['concentrations'] if x > cutoff])
            assert v['n'] == int(row[f'native_denominator_{y}']) == int(row[f'threshold_denominator_{y}'])
            assert v['detected'] == int(row[f'native_numerator_{y}'])
            assert numerator == int(row[f'threshold_numerator_{y}'])
            native_rates.append(Fraction(v['detected'], v['n']))
            threshold_rates.append(Fraction(numerator, v['n']))
        delta1 = native_rates[1] - native_rates[0]; delta2 = threshold_rates[1] - threshold_rates[0]
        sign1 = 0 if delta1 == 0 else 1 if delta1 > 0 else -1
        sign2 = 0 if delta2 == 0 else 1 if delta2 > 0 else -1
        assert sign1 == int(row['native_direction']) and sign2 == int(row['threshold_direction'])
        assert abs(float(delta1 * 100) - float(row['native_delta_pp'])) < 1e-12
        assert abs(float(delta2 * 100) - float(row['threshold_delta_pp'])) < 1e-12
        checks.append(dict(code=code, multiplier=multiplier, verified=True))
    sources = json.loads((OUT / 'source_provenance.json').read_text())
    for source in sources:
        assert sha(Path(source['path'])) == source['sha256']
    assert sha(PROTOCOL) == summary['protocol_sha256']
    receipt = dict(status='PASS', checked_utc=datetime.now(timezone.utc).isoformat(),
        checked_common_dispositions=len(dispositions), independently_parsed_reference_codes=code_names,
        checked_eligible_comparisons=len(checks), checked_eligible_codes=len(eligible),
        selected_source_hashes_unchanged=2, parent_freeze_verified=freeze_check(),
        implementation='Direct pipe-string splitting; pypdf reference extraction; Fraction arithmetic; no calls to production classification or direction functions.',
        scope='Independent implementation within the same AI-assisted project, not independent personnel or scientific validation.',
        script_sha256=sha(Path(__file__)), summary_sha256=sha(OUT / 'summary.json'))
    dump('separate_arithmetic_verification.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--lock', action='store_true')
    group.add_argument('--run', action='store_true')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        lock() if args.lock else run() if args.run else verify()
    except Exception as error:
        if OUT.is_dir():
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            dump(f'failure_{stamp}.json', dict(type=type(error).__name__, message=str(error),
                stage='lock' if args.lock else 'run' if args.run else 'verify', script_sha256=sha(Path(__file__))))
        raise
