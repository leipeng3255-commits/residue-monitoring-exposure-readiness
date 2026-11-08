"""Read-only source replay. New outputs only; frozen inputs never changed."""
import argparse, collections, csv, hashlib, io, json, zipfile
from decimal import Decimal
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
CFG = {k.strip(): json.loads(v.strip()) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
       if line and not line.startswith('#') for k, v in [line.split(':', 1)]}
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, default=ROOT/'00_admin/verification_extension_v21')
OUT = parser.parse_args().out
OUT.mkdir(exist_ok=True)
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()
def close(a, b):
    a, b = Decimal(str(a)), Decimal(str(b))
    return abs(a-b) <= max(Decimal('1e-12'), abs(b)*Decimal('1e-10'))
def save(name, value):
    with (OUT/name).open('x') as f: json.dump(value, f, indent=2, ensure_ascii=False)

manifest = json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text())
freeze = [{'path': x['path'], 'pass': sha(Path(x['path'])) == x['sha256']} for x in manifest['files']]
assert all(x['pass'] for x in freeze)
master = ROOT/'08_manuscript/final_food_control_version/revision_v20_language_polish/tables/chronic_exposure_master.csv'
rows = list(csv.DictReader(master.open()))
exports = [x for x in manifest['files'] if x['path'].endswith('_detailed.xlsx')]
index = collections.defaultdict(list)
for r in rows:
    for bound in ('LB', 'UB'): index[r['output_sha256_'+bound]].append((bound, r))
failures = []; counts = collections.Counter(); dimensions = []; per_file = []
for entry in exports:
    path = Path(entry['path']); wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    dimensions.append({'filename': path.name, 'declared_rows': sheet.max_row, 'declared_columns': sheet.max_column})
    # Native export XML understates dimensions. Ignore that metadata, not the cells.
    sheet.reset_dimensions()
    values = iter(sheet.values); headers = next(values)
    records = [dict(zip(headers, r)) for r in values if any(v is not None for v in r)]
    native = {(r['Country'], r['Survey'], r['Popclass']): r for r in records}
    assert len(native) == len(records), path
    targets = index[entry['sha256']]
    assert len(targets) == 88 and len(native) == 88, path
    expected_keys = {(r['survey_country'], r['survey'], r['population_group']) for _,r in targets}
    assert expected_keys == set(native), path
    for bound, r in targets:
        key = (r['survey_country'], r['survey'], r['population_group']); n = native[key]
        if str(n['N subjects']) != r['survey_n']: failures.append([path.name, key, 'subject_n'])
        if n['HBGV Unit'] != 'mg/kg bw/day' or n['HBGV Type'] != 'ADI': failures.append([path.name,key,'HBGV_units'])
        if not close(n['HBGV Value'], r['adi_mg_kg_bw_day']): failures.append([path.name,key,'ADI'])
        if n['HRP Comment'] != r['HRP_percentile']: failures.append([path.name,key,'HRP_percentile'])
        for metric, exposure, percent in [('mean','Mean Exposure (µg/kg bw per day)','Mean exposure % ADI'),
                                          ('HRP','HRP (µg/kg bw per day)','HRP (% ADI)')]:
            for native_col, csv_col in [(exposure, f'exposure_{metric}_{bound}_ug_kg_bw_day'),
                                        (percent, f'percent_ADI_{metric}_{bound}')]:
                counts['native_numeric_comparisons'] += 1
                if not close(n[native_col], r[csv_col]): failures.append([path.name,key,csv_col])
            recalculated = Decimal(str(n[exposure])) / (Decimal(str(n['HBGV Value']))*1000) * 100
            counts['ADI_recalculations'] += 1
            if not close(recalculated,n[percent]): failures.append([path.name,key,'Decimal_ADI_'+metric])
        counts['native_records'] += 1
    per_file.append({'path': str(path), 'sha256': entry['sha256'], 'records': len(records)})
    wb.close()
save('native_export_verification.json', {'frozen_files':len(freeze),'frozen_pass':sum(x['pass'] for x in freeze),
    'master_sha256':sha(master),'native_exports':len(exports),'counts':dict(counts),'failures':failures,
    'tolerance':'absolute 1e-12 or relative 1e-10, whichever is larger; export rounding only',
    'dimension_metadata':dimensions,'files':per_file,
    'boundary':'Original native Excel values checked, not reconstruction of hosted engine or laboratory assays.'})

# Prespecified spinach absence is retained; no favourable commodity substitution.
archive = Path(CFG['raw_data_root'])/'other/2024PDPDatabase.zip'; before = sha(archive)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    wb = openpyxl.load_workbook(io.BytesIO(z.read('PDP ReferenceTables 2024.xlsx')),read_only=True,data_only=True)
    catalogue = list(wb['Commodity'].values)
    spinach = [list(r) for r in catalogue if any('spinach' in str(v).lower() for v in r)]
    dictionary = {name:[list(r) for r in wb[name].values] for name in ['Commodity','Commod Type','Mean','Annotate','Con Unit']}
    save('pdp_dictionary_evidence.json', dictionary)
    save('prespecified_spinach_application.json', {'archive_sha256':before,'matching_catalogue_rows':spinach,
        'status':'ABSENT_APPLICATION_STOPPED' if not spinach else 'PRESENT_REQUIRES_SEPARATE_AUDIT',
        'new_commodity_outcomes_inspected':False,'alternative_selected':False})
    # Replay the completed CT application, transparently NOT the new spinach test.
    samples = {}; duplicates = 0
    for row in csv.reader(io.TextIOWrapper(z.open('PDP24Samples.txt')),delimiter='|'):
        if row[0] in samples: duplicates += 1
        samples[row[0]] = row
    selected = {k:r for k,r in samples.items() if r[6]=='CT'}
    keys = collections.Counter(); flags = collections.Counter(); units = collections.Counter()
    panels = collections.defaultdict(set); errors = collections.Counter(); result_n = 0
    for r in csv.reader(io.TextIOWrapper(z.open('PDP24Results.txt')),delimiter='|'):
        if r[1] != 'CT': continue
        result_n += 1; keys[(r[0],r[4])] += 1; panels[r[0]].add(r[4]); flags[r[13]] += 1; units[r[8]] += 1
        if r[0] not in selected: errors['orphan'] += 1
        elif selected[r[0]][12] != r[2]: errors['form_mismatch'] += 1
        try:
            if Decimal(r[7]) <= 0: errors['nonpositive_LOD'] += 1
        except Exception: errors['invalid_LOD'] += 1
        if r[13]=='ND' and r[6].strip(): errors['ND_with_concentration'] += 1
    support = collections.Counter(p for k,p in keys)
    actual = {'selected_samples':len(selected),'selected_result_rows':result_n,'analyte_codes':len(support),
        'result_flags':dict(flags),'concentration_units':dict(units),'duplicate_sample_keys_all':duplicates,
        'duplicate_sample_analyte_keys':sum(n>1 for n in keys.values()),
        'per_sample_analyte_count_min':min(map(len,panels.values())), 'per_sample_analyte_count_max':max(map(len,panels.values())),
        'tested_samples_per_analyte_min':min(support.values()),'tested_samples_per_analyte_max':max(support.values())}
    previous = json.loads((ROOT/'00_admin/independent_source_application_20260928/structural_audit.json').read_text())
    agreement = {k:actual[k]==previous[k] for k in actual}
    assert all(agreement.values()) and not errors
    save('cross_programme_replay.json', {'archive_sha256_before':before,'archive_sha256_after':sha(archive),
        'actual':actual,'agreement_with_saved_application':agreement,'structural_errors':dict(errors),
        'unrecorded_sample_analyte_combinations':len(selected)*len(support)-len(keys),
        'exposure_additions':0,'boundary':'Replay of existing cross-programme CT case; not new external validation or chemical/dietary admission.'})
assert before == sha(archive)
assert not failures
print(json.dumps({'native_exports':len(exports),'counts':dict(counts),'native_failures':len(failures),
    'spinach_present':bool(spinach),'PDP_replay':actual},ensure_ascii=False))
