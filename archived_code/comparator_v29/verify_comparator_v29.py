"""Reconcile saved comparators to source endpoints and independently tally decisions."""
import argparse,collections,csv,hashlib,json
from pathlib import Path
from fractions import Fraction
import yaml
ROOT=Path(__file__).resolve().parents[2];cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
WORK=ROOT/'08_manuscript/comparator_v29'
COMMON=ROOT/'10_submission/最终投稿材料_v28_预设来源检验_文件夹版/03_可复现数据与代码_NOT_DIRECT_UPLOAD'
DATA=Path(cfg['intermediate_data_root'])/'comparator_v29_20261013'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=WORK);args=ap.parse_args()
OUT=args.out;OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/'comparison_verification.json').exists()
cases=json.loads((WORK/'cases.json').read_text());byid={c['case_id']:c for c in cases}
source_checks=0
for path,family,key,lo,hi in [
 ('tables/cell_diagnostics.csv','single_food_mean_reference',None,'max_mean_percent_ADI_LB','max_mean_percent_ADI_UB'),
 ('tables/same_chemical_ratio_bounds.csv','same_chemical_CZ_DE_order','pesticide','ratio_lower','ratio_upper'),
 ('evidence_extension_v22/paired_concentration_bounds.csv','selected_production_group_order','pesticide','difference_LB_mg_kg','difference_UB_mg_kg')]:
    for r in read(COMMON/path):
        ident=r[key] if key else r['occurrence_country']+'|'+r['pesticide']
        c=byid['REAL|'+family+'|'+ident]
        assert (Fraction(c['lower']),Fraction(c['upper']))==(Fraction(r[lo]),Fraction(r[hi]));source_checks+=1
assert source_checks==37
rows=read(DATA/'case_results.csv');assert len(rows)==450
fair=[r for r in rows if r['arm'] in ('DIRECT_GUIDANCE','FRAMEWORK')]
assert all(r['result']==r['expected'] and r['exact_reference_match']=='1' for r in fair)
dispositions=[]
for family in dict.fromkeys(r['family'] for r in rows):
    for arm in dict.fromkeys(r['arm'] for r in rows):
        rr=[r for r in rows if r['family']==family and r['arm']==arm]
        ct=collections.Counter('held' if r['result'].startswith('HOLD') else 'unresolved' if r['result']=='CENSORING_UNRESOLVED' else 'definitive_output' for r in rr)
        dispositions.append({'family':family,'arm':arm,'n':len(rr),**{k:ct[k] for k in ['definitive_output','unresolved','held']}})
        assert sum(ct.values())==len(rr)
        for r in rr:
            expected_supported=not r['expected'].startswith('HOLD') and r['expected']!='CENSORING_UNRESOLVED'
            got_supported=not r['result'].startswith('HOLD') and r['result']!='CENSORING_UNRESOLVED'
            assert int(r['unsupported_permission'])==int(got_supported and not expected_supported)
            assert int(r['unnecessary_withholding'])==int(expected_supported and not got_supported)
with (OUT/'disposition_counts.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(dispositions[0]));w.writeheader();w.writerows(dispositions)
summary=read(DATA/'family_summary.csv')
for r in summary:
    rr=[s for s in rows if s['family']==r['family'] and s['arm']==r['arm']]
    for metric in ['exact_reference_match','unsupported_permission','unnecessary_withholding','wrong_definitive_label','wrong_numeric_endpoint']:
        assert int(r[metric])==sum(int(s[metric]) for s in rr)
receipt={'status':'PASS','original_endpoint_records_reconciled':source_checks,'case_arm_rows_recounted':450,'fair_predictions':180,'families_separate':True,'independent_human_evaluation':False,'disposition_counts_sha256':sha(OUT/'disposition_counts.csv'),'scope':'Independent tally implementation, same project and data; not external gold-standard validation. definitive_output is a returned answer, not necessarily a supported answer in ablation arms.'}
(OUT/'comparison_verification.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
