"""Post-freeze algebraic diagnostics; no new exposure scenarios or raw-data edits."""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
PATHS = yaml.safe_load((ROOT / '00_admin/paths.yaml').read_text())
assert Path(PATHS['data_root']).is_dir()
BASE = ROOT / '08_manuscript/final_food_control_version/revision_v18_author_information/tables'
OUT = ROOT / '08_manuscript/comprehensive_review_v19'
OUT.mkdir(exist_ok=True)
(OUT / 'tables').mkdir(exist_ok=True)
inputs = {}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):
    p = BASE / name
    inputs[name] = sha(p)
    with p.open() as f:
        return list(csv.DictReader(f))
def write(name, rows):
    with (OUT / 'tables' / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

freeze = json.loads((ROOT / '00_admin/analysis_freeze_manifest_20260921.json').read_text())
assert all(sha(Path(x['path'])) == x['sha256'] for x in freeze['files'])
master = read('chronic_exposure_master.csv')
cells = read('cell_diagnostics.csv')
assert len(master) == 1672 and len(cells) == 19
byunit = defaultdict(list)
q_bystratum = defaultdict(list)
adi_errors = []
for r in master:
    key = (r['occurrence_country'], r['pesticide'])
    byunit[key].append(r)
    skey = (r['survey_country'], r['survey'], r['population_group'])
    for end in ['LB', 'UB']:
        for measure in ['mean', 'HRP']:
            observed = float(r[f'percent_ADI_{measure}_{end}'])
            calculated = float(r[f'exposure_{measure}_{end}_ug_kg_bw_day']) / (10 * float(r['adi_mg_kg_bw_day']))
            assert math.isclose(calculated, observed, rel_tol=1e-10, abs_tol=1e-12)
            adi_errors.append(abs(calculated-observed))
        # Native export E in ug/kg-bw/day; C in mg/kg-food, so divide by 1000.
        q = float(r[f'exposure_mean_{end}_ug_kg_bw_day']) / (1000 * float(r[f'occurrence_{end}_mg_kg']))
        q_bystratum[skey].append(q)
linear = []
def skey(r):
    return '|'.join(r[k] for k in ['survey_country', 'survey', 'population_group'])
for key, rows in sorted(byunit.items()):
    assert len(rows) == 88 and len({skey(r) for r in rows}) == 88
    mean_lb = max(rows, key=lambda r: float(r['percent_ADI_mean_LB']))
    mean_ub = max(rows, key=lambda r: float(r['percent_ADI_mean_UB']))
    hrp_ub = max(rows, key=lambda r: float(r['percent_ADI_HRP_UB']))
    assert skey(mean_lb) == skey(mean_ub)
    linear.append(dict(occurrence_country=key[0], pesticide=key[1],
        mean_LB_max_stratum=skey(mean_lb), mean_UB_max_stratum=skey(mean_ub),
        HRP_UB_max_stratum=skey(hrp_ub), LB_UB_mean_maximiser_matches=True))
q_spread = max((max(x)-min(x))/max(x) for x in q_bystratum.values())
assert q_spread < 1e-9
write('native_linear_scaling_checks.csv', linear)

comparisons = read('same_chemical_comparisons.csv')
ratios = []
for r in comparisons:
    l1,u1,l2,u2 = (float(r[k]) for k in ['occurrence_LB_i','occurrence_UB_i','occurrence_LB_j','occurrence_UB_j'])
    assert min(l1,l2) > 0
    low, high = l1/u2, u1/l2
    # Same pesticide / fixed diet cancels q and ADI. No midpoint estimate is assumed.
    for row in byunit[('CZ', r['unit_i'][3:])]:
        other = next(x for x in byunit[('DE', r['unit_i'][3:])] if skey(x)==skey(row))
        assert math.isclose(float(row['percent_ADI_mean_LB']) / float(other['percent_ADI_mean_UB']), low, rel_tol=1e-9)
        assert math.isclose(float(row['percent_ADI_mean_UB']) / float(other['percent_ADI_mean_LB']), high, rel_tol=1e-9)
    ratios.append(dict(pesticide=r['unit_i'][3:], numerator='CZ sampled-lot mean', denominator='DE sampled-lot mean',
        ratio_lower=low, ratio_upper=high, includes_one=low<=1<=high,
        CZ_samples=r['sample_n_i'], DE_samples=r['sample_n_j'], matched_diet_strata_checked=88,
        interpretation='Censoring identification interval only; no sampling uncertainty or national exposure inference'))
write('same_chemical_ratio_bounds.csv', ratios)

nd = read('all_nondetect_sample_audit.csv')
counts=Counter((r['chemical'],float(r['limit_mg_kg'])) for r in nd)
nd_summary=[]
for chemical in sorted({r['chemical'] for r in nd}):
    rows=[r for r in nd if r['chemical']==chemical]
    assert len(rows)==len({r['sample_id'] for r in rows})==214
    assert {r['result_type'] for r in rows}=={'LOQ'}
    for (chem,lim),n in sorted(counts.items()):
        if chem==chemical:nd_summary.append(dict(chemical=chem,LOQ_mg_kg=lim,sample_chemical_records=n,denominator=214))
write('nondetect_limit_distribution.csv',nd_summary)

receipt=dict(status='PASS', scope='Frozen-export arithmetic and descriptive algebra; not new model output or independent human validation',
    frozen_files_verified=len(freeze['files']), input_sha256=inputs, native_rows=len(master),
    percent_ADI_checks=len(adi_errors), max_absolute_percent_ADI_error=max(adi_errors),
    mean_LB_UB_maximiser_matches=sum(x['LB_UB_mean_maximiser_matches'] for x in linear),
    dietary_strata=len(q_bystratum), maximum_relative_native_intake_coefficient_spread=q_spread,
    same_chemical_pairs=len(ratios), matched_pair_strata_checked=3*88,
    nondetect_records_checked=len(nd), same_chemical_ratio_bounds=ratios)
(OUT/'calculation_validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='input_sha256'},indent=2))
