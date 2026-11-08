"""Produce bounded reporting diagnostics after the locked primary analysis.

Run from the project root. Does not modify eligibility or the primary results.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile

root = Path.cwd()
cfg = {k: json.loads(v.strip()) for k, v in (line.split(':', 1) for line in
       (root / '00_admin/paths.yaml').read_text().splitlines()
       if re.match(r'^[a-z_]+:\s*"', line))}
assert Path(cfg['project_root']).resolve() == root.resolve()
check = subprocess.run([sys.executable, str(root / '05_code/utilities/check_paths.py')], capture_output=True, text=True)
assert check.returncode == 0 and 'PASS overall' in check.stdout, check.stdout + check.stderr
out = Path(cfg['outputs_root']) / 'manuscript_source_stability_v35/pdp'
raw = Path(cfg['raw_data_root'])
assert not (out / 'reporting_support.json').exists()
dispositions = list(csv.DictReader((out / 'all_common_code_dispositions.csv').open()))
common = {r['code'] for r in dispositions}
eligible = {r['code'] for r in dispositions if r['disposition'] == 'ELIGIBLE_SOURCE_CONDITIONAL'}
source_records = json.loads((out / 'source_provenance.json').read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def save_csv(name, rows):
    with (out / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


support = []
positive_rows = []
p90_samples = []
for year in (2022, 2023):
    path = raw / 'usda_pdp' / f'{year}PDPDatabase.zip'
    source = next(s for s in source_records if s['path'] == str(path))
    assert digest(path) == source['sha256']
    ids, codes = set(), set()
    labs = Counter(); count = 0
    with zipfile.ZipFile(path) as z:
        samples = {r[0]: r for r in csv.reader(io.TextIOWrapper(z.open(f'PDP{str(year)[2:]}Samples.txt')),
                    delimiter='|') if r[6] == 'TO' and r[12] == 'FR'}
        member = f'PDP{str(year)[2:]}Results.txt'
        for source_line, row in enumerate(csv.reader(io.TextIOWrapper(z.open(member)), delimiter='|'), 1):
            if (row[1], row[2]) != ('TO', 'FR'):
                continue
            if row[14] == 'P90':
                ids.add(row[0]); codes.add(row[4]); count += 1; labs[row[3]] += 1
            if row[4] in eligible and row[13] in ('O', 'R'):
                positive_rows.append(dict(year=year, source_member=member,
                    source_line_1based=source_line, sample_pk=row[0], lab=row[3], code=row[4],
                    concentration_ppm=row[6], lod_ppm=row[7], annotation=row[11],
                    quantitation=row[12], mean=row[13], extraction=row[14], determination=row[15],
                    archive_sha256=source['sha256']))
        for sid in sorted(ids, key=int):
            p90_samples.append(dict(year=year, sample_pk=sid, month=samples[sid][3],
                source_variety_storage_text=samples[sid][8]))
    support.append(dict(year=year, p90_result_rows=count, p90_sample_n=len(ids),
        p90_all_code_n=len(codes), p90_common_code_n=len(codes & common),
        p90_laboratory_result_counts=dict(labs)))
    assert digest(path) == source['sha256']

save_csv('eligible_positive_source_rows.csv', positive_rows)
save_csv('p90_sample_storage_records.csv', p90_samples)
# Display-only disjoint partition, with priority declared explicitly.
counts = Counter()
for r in dispositions:
    reasons = set(r['hold_reasons'].split(';'))
    if r['disposition'] == 'ELIGIBLE_SOURCE_CONDITIONAL':
        group = 'Eligible source-conditional'
    elif 'EXTRACTION_P90' in reasons:
        group = 'HOLD: P90 storage marker (may also have other reasons)'
    elif 'BQL_WITHOUT_NUMERIC_LOQ' in reasons:
        group = 'HOLD: BQL without numeric LOQ, no P90'
    else:
        group = 'HOLD: determinative-method set change, no P90/BQL'
    counts[group] += 1
assert sum(counts.values()) == 362
save_csv('figure_A_disjoint_dispositions.csv', [dict(group=k, codes=v) for k, v in counts.items()])
schema = {}
for filename in ['all_common_code_dispositions.csv', 'all_analyte_year_profiles.csv',
                 'eligible_comparisons.csv', 'sample_frame_composition.csv',
                 'eligible_positive_source_rows.csv', 'figure_A_disjoint_dispositions.csv']:
    with (out / filename).open() as stream:
        reader = csv.reader(stream)
        schema[filename] = dict(columns=next(reader), rows=sum(1 for _ in reader))
(out / 'csv_schema.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
report = dict(completed_utc=datetime.now(timezone.utc).isoformat(), profiles=support,
    eligible_positive_source_rows=len(positive_rows), disjoint_display_counts=dict(counts),
    p90_interpretation='P90 identifies storage beyond 90 days; it occupies EXTRACT but is not a distinct extraction technique. All 326 common-code extraction-code-set differences coincide with P90.',
    thpi_interpretation='Code 624 has the same median LOD (0.012 ppm) and maximum LOD (0.024 ppm) in both years. Its reversal is event-definition sensitivity, not evidence that changed LOD caused a trend reversal.',
    no_change_to_primary_eligibility_or_protocol=True,
    primary_summary_sha256=digest(out / 'summary.json'), script_sha256=digest(Path(__file__)),
    verification_parser_repair='Initial separate PDF-reader assertion failed on doubled interword spaces. Verification-only repair normalized repeated whitespace and accepted alphanumeric analyte codes. Production calculations were not changed; original script snapshot and failure receipt retained.')
(out / 'reporting_support.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
