"""Bounded feasibility profiles; source files read-only, no exposure estimates."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv, hashlib, io, json, re, statistics, subprocess, zipfile
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
CFG = {k: json.loads(v.strip()) for k, v in (line.split(':', 1) for line in
       (ROOT/'00_admin/paths.yaml').read_text().splitlines() if re.match(r'^[a-z_]+:\s*"', line))}
assert Path(CFG['project_root']).resolve() == ROOT
RAW = Path(CFG['raw_data_root'])
OUT = Path(CFG['outputs_root'])/'diagnostics/depth_feasibility_20261015'
assert RAW.is_dir() and not OUT.exists()
manifest_path = ROOT/'00_admin/download_manifest.csv'
manifest_bytes = manifest_path.read_bytes()
manifest = list(csv.DictReader(io.StringIO(manifest_bytes.decode('utf-8-sig'))))
by_path = defaultdict(list)
for row in manifest:
    by_path[row['local_file_path']].append(row)
sources = []

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for data in iter(lambda: handle.read(1048576), b''):
            h.update(data)
    return h.hexdigest()

def verify(path):
    assert path.is_file() and path.is_relative_to(RAW)
    digest = sha(path)
    matching = [r for r in by_path[str(path)] if r['sha256'] == digest and int(r['bytes']) == path.stat().st_size]
    assert matching, str(path)
    sources.append(dict(path=str(path), size=path.stat().st_size, sha256=digest,
                        url=matching[0]['official_url'], filename=matching[0]['original_filename']))
    return digest

def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n')

def frozen_check():
    files = json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text())['files']
    assert len(files) == 95
    for r in files:
        assert sha(Path(r['path'])) == r['sha256']
    return len(files)

freeze_before = frozen_check()
pdp = []
panels = {}
tomato_detail = []
for year in range(2020, 2025):
    path = RAW/('other' if year == 2024 else 'usda_pdp')/f'{year}PDPDatabase.zip'
    verify(path)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        sample_member = next(n for n in z.namelist() if 'Samples' in n and n.endswith('.txt'))
        rows = list(csv.reader(io.TextIOWrapper(z.open(sample_member), encoding='utf-8-sig'), delimiter='|'))
        assert all(len(r) == 18 for r in rows)
        assert len({r[0] for r in rows}) == len(rows)
        counts = Counter((r[6], r[12]) for r in rows)
        panels[year] = set(counts)
        item = dict(year=year, sample_records=len(rows), unique_sample_pk=len(rows),
                    commodity_form_units=len(counts),
                    counts=[dict(commodity=k[0], form=k[1], n=v) for k,v in sorted(counts.items())])
        # Metadata-selected application: same TO/FR code in two adjacent years.
        # No concentration, effect, or detection-rate selection is used.
        if year in (2022, 2023):
            dictionary = next(n for n in z.namelist() if 'DataDictionary' in n and n.endswith('.pdf'))
            text = subprocess.run(['pdftotext','-layout','-','-'],input=z.read(dictionary),capture_output=True,check=True).stdout.decode()
            assert all(x in text for x in ['SAMPLE_PK','PESTCODE','LOD','CONUNIT','ANNOTATE','MEAN'])
            sample_map = {r[0]:r for r in rows}
            chosen = {r[0]:r for r in rows if (r[6],r[12]) == ('TO','FR')}
            analytes = defaultdict(lambda: dict(ids=set(), rows=0, lods=[], units=Counter(),
                               flags=Counter(), annotations=Counter(), labs=set(), concentration_nonempty=0))
            member = next(n for n in z.namelist() if 'Results' in n and n.endswith('.txt'))
            n_all = n_selected = bad_foreign = duplicate_keys = 0
            seen = set()
            for r in csv.reader(io.TextIOWrapper(z.open(member), encoding='utf-8-sig'),delimiter='|'):
                n_all += 1
                assert len(r) == 16
                if (r[1],r[2]) != ('TO','FR'):
                    continue
                n_selected += 1
                if r[0] not in chosen:
                    bad_foreign += 1
                key = (r[0],r[4])
                duplicate_keys += int(key in seen)
                seen.add(key)
                a = analytes[r[4]]
                a['ids'].add(r[0]); a['rows'] += 1
                a['units'][r[8]] += 1; a['flags'][r[13]] += 1
                a['annotations'][r[11]] += 1; a['labs'].add(r[3])
                a['concentration_nonempty'] += int(bool(r[6].strip()))
                a['lods'].append(float(r[7]))
            assert bad_foreign == 0
            for code, a in sorted(analytes.items()):
                assert min(a['lods']) > 0
                tomato_detail.append(dict(year=year, pesticide_code=code, tested_samples=len(a['ids']),
                    sample_frame=len(chosen), result_rows=a['rows'], units=dict(a['units']),
                    flags=dict(a['flags']), annotations=dict(a['annotations']), labs=sorted(a['labs']),
                    lod_min=min(a['lods']), lod_median=statistics.median(a['lods']), lod_max=max(a['lods']),
                    concentration_nonempty=a['concentration_nonempty']))
            item['tomato_feasibility'] = dict(commodity='TO',form='FR',sample_n=len(chosen),
                full_archive_result_rows_read=n_all,selected_result_rows=n_selected,
                analyte_codes=len(analytes),duplicate_sample_analyte_keys=duplicate_keys,
                foreign_key_failures=bad_foreign,
                monthly_samples=dict(sorted(Counter(r[3] for r in chosen.values()).items())),
                origin_codes=dict(Counter(r[9] for r in chosen.values())),
                marketing_claims=dict(Counter(r[13] for r in chosen.values())))
        pdp.append(item)
print('PDP source profiles complete', flush=True)

td = {(r['year'],r['pesticide_code']):r for r in tomato_detail}
codes22 = {c for y,c in td if y == 2022}; codes23 = {c for y,c in td if y == 2023}
shared = codes22 & codes23
unit_compatible = [c for c in shared if list(td[2022,c]['units']) == list(td[2023,c]['units']) == ['M']]
pdp_comparison = dict(common_commodity_forms_all_five_years=sorted(set.intersection(*panels.values())),
    adjacent_overlap={f'{y}-{y+1}':len(panels[y]&panels[y+1]) for y in range(2020,2024)},
    tomato_common_analyte_codes=len(shared), tomato_2022_only_codes=sorted(codes22-codes23),
    tomato_2023_only_codes=sorted(codes23-codes22), common_codes_with_same_ppm_unit=len(unit_compatible),
    common_ppm_codes_changed_median_lod=sum(td[2022,c]['lod_median'] != td[2023,c]['lod_median'] for c in unit_compatible),
    common_ppm_codes_changed_max_lod=sum(td[2022,c]['lod_max'] != td[2023,c]['lod_max'] for c in unit_compatible),
    common_codes_not_tested_in_all_samples_either_year=sum(any(td[y,c]['tested_samples'] < td[y,c]['sample_frame'] for y in [2022,2023]) for c in shared),
    caveat='Code overlap is not certified chemical-definition equivalence. These are feasibility profiles, not exposure or population trends.')

def workbook_rows(data, sheet):
    w = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    return list(w[sheet].values)

aus_path = Path(next(r['local_file_path'] for r in manifest if r['original_filename']=='AUSNUT 2023 - All Files_0.zip'))
verify(aus_path)
with zipfile.ZipFile(aus_path) as z:
    assert z.testzip() is None
    def member(suffix):
        return next(n for n in z.namelist() if n.endswith(suffix))
    food = [r for r in workbook_rows(z.read(member('Food details.xlsx')),'Food details')[4:] if r[0] is not None]
    assert len(food) == len({r[0] for r in food}) == 3741
    recipes = {}
    for key, suffix, sheet in [('nutrient','Food nutrient recipes.xlsx','Food nutrient recipes'),
                               ('adg','Australian Dietary Guidelines recipes.xlsx','ADG Recipes')]:
        a = [r for r in workbook_rows(z.read(member(suffix)),sheet)[3:] if r[0] is not None]
        groups = defaultdict(list)
        for row in a:
            groups[row[0]].append(row)
        recipes[key] = (a,groups)
    match = [r for r in workbook_rows(z.read(member('Matching file.xlsx')),'TAB A - Matching file')[4:] if r[1] is not None]
    assert len(match) == 3741
    r_n,r_a = recipes['nutrient'][1],recipes['adg'][1]
    both = set(r_n)&set(r_a)
    def signature(rows):
        return sorted((str(r[4]),str(r[5]),str(r[7]),str(r[3])) for r in rows)
    differences = [k for k in sorted(both) if signature(r_n[k]) != signature(r_a[k])]
    aus = dict(food_records=len(food),derivation_counts=dict(Counter(r[3] for r in food)),
        recipe_rows={k:len(v[0]) for k,v in recipes.items()},
        recipe_food_counts={k:len(v[1]) for k,v in recipes.items()},
        foods_with_both_recipe_types=len(both), different_ingredient_weight_or_yield_signatures=len(differences),
        difference_definition='Exact multiset of ingredient survey ID, public food key, source ingredient grams and source weight-change percent; differences are purpose-specific, not source errors.',
        matching_2023_foods_with_old_code=sum(r[3] is not None for r in match),
        matching_2023_foods_without_old_code=sum(r[3] is None for r in match),
        tomato_named_ingredient_links={k:sum('tomato' in str(r[6]).lower() for r in v[0]) for k,v in recipes.items()},
        caution='Tomato substring is only a feasibility locator, not a vegetable crosswalk. Nutrient/ADG recipes are not pesticide processing factors or actual person-level consumption.')
print('AUSNUT source profiles complete', flush=True)

nz = []
nz_maps = {}
for path in sorted(RAW.glob('new_zealand_mpi_total_diet_study/2024_Q*/*.xlsx')):
    if path.name.startswith('._') or path.stat().st_size < 1000000:
        continue  # Fixed selected multiresidue workbooks; single-residue files are not analysed.
    verify(path)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
    w = load_workbook(path,read_only=True,data_only=True)
    title = [r[0] for r in w['Contents'].iter_rows(min_row=1,max_row=6,max_col=1,values_only=True) if r[0]]
    s=w['Table 1.1 All results']; rows=list(s.values); header=rows[0]
    result_columns=[i for i,v in enumerate(header) if v and str(v).startswith('Quarter')]
    grouped=defaultdict(list)
    unit_column=header.index('Unit')
    for excel_row,row in enumerate(rows[2:],3):
        if not row[0] or not row[2]:
            continue
        key=tuple(row[:3])+(row[unit_column],)
        grouped[key].append(dict(excel_row=excel_row, full_row=list(row),
                                values={header[i]:row[i] for i in result_columns}))
    duplicates=[dict(key=k,records=v,identical_full_rows=all(x['full_row']==v[0]['full_row'] for x in v))
                for k,v in grouped.items() if len(v)>1]
    # Retain every source row. Ambiguous identities are not arbitrarily collapsed.
    maps={k:v[0]['values'] for k,v in grouped.items() if len(v)==1}
    quarter=path.parent.name[-2:];nz_maps[quarter]=(maps,set(grouped))
    states=Counter()
    for row in (entry['values'] for entries in grouped.values() for entry in entries):
        for value in row.values():
            if value is None: states['blank'] += 1
            elif isinstance(value,(int,float)): states['numeric'] += 1
            elif str(value).strip().startswith('<'): states['left_censored'] += 1
            else: states[str(value).strip()] += 1
    nz.append(dict(file=path.name,quarter_label=quarter,source_titles=title,
                   source_data_rows=sum(len(v) for v in grouped.values()),distinct_keys=len(grouped),
                   unambiguous_row_keys=len(maps), distinct_food_labels=len({k[0] for k in grouped}),
                   result_columns=[header[i] for i in result_columns],source_cell_states=dict(states),
                   duplicate_key_groups=len(duplicates),duplicate_extra_rows=sum(len(v)-1 for v in grouped.values()),
                   duplicate_records_preserved=duplicates))
nz_compare=[]
for earlier,later in [('Q1','Q3'),('Q2','Q4')]:
    (a,all_a),(b,all_b)=nz_maps[earlier],nz_maps[later]; common=set(a)&set(b)
    checked=different=0
    differences=[]
    for key in common:
        for column,value in a[key].items():
            assert column in b[key]
            checked+=1;different+=int(value != b[key][column])
            if value != b[key][column]:
                differences.append(dict(key=key,column=column,earlier_value=value,later_value=b[key][column]))
    nz_compare.append(dict(earlier=earlier,later=later,overlapping_row_keys=len(common),
                          ambiguous_overlap_keys_excluded=len((all_a&all_b)-common),
                          earlier_keys_absent_later=len(all_a-all_b),new_row_keys_in_later=len(all_b-all_a),
                          repeated_earlier_quarter_cells=checked,changed_repeated_values=different,
                          changed_cells_preserved=differences))
print('NZ source profiles complete', flush=True)

for row in sources:
    assert sha(Path(row['path'])) == row['sha256']
freeze_after=frozen_check()
OUT.mkdir(parents=True)
dump('source_provenance.json',sources)
dump('pdp_sample_and_tomato_profiles.json',pdp)
dump('pdp_tomato_analyte_profiles.json',tomato_detail)
dump('pdp_temporal_feasibility.json',pdp_comparison)
dump('ausnut_recipe_feasibility.json',aus)
dump('nz_quarter_structure.json',dict(profiles=nz,repeated_quarter_checks=nz_compare,
    source_legend=dict(left_censored='At the LOQ',NR='Not reported due to methodological issues',
                       NA='Not available; sample not tested for this chemical'),
    initial_failed_attempt='Unique commodity-group-compound assertion failed in Q4. Read-only inspection found four identical duplicate-row groups. Final audit preserves all rows and excludes ambiguous keys from paired checks; no source data were corrected.'))
receipt=dict(date='2026-10-15',finished_utc=datetime.now(timezone.utc).isoformat(),
    manifest_snapshot_rows=len(manifest),manifest_snapshot_unique_paths=len(by_path),
    manifest_snapshot_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    selected_raw_files_verified=len(sources),raw_files_rehashed_after=len(sources),
    frozen_before=freeze_before,frozen_after=freeze_after,
    new_exposure_estimates=0,new_downloads=0,manuscript_modified=False,
    script_sha256=sha(Path(__file__)),
    limits='Read-only source feasibility audit with derived profiles; not a prespecified unseen validation, independent personnel test, global census or manuscript-integrated result.')
dump('audit_receipt.json',receipt)
print(json.dumps(dict(receipt=receipt,pdp=pdp_comparison,ausnut=aus,
    nz=[{k:v for k,v in r.items() if k!='changed_cells_preserved'} for r in nz_compare]),ensure_ascii=False,indent=2))
