"""Reconstruct the archived 262-key frame, without extending its scope."""
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[2]
cfg = yaml.safe_load((ROOT / '00_admin/paths.yaml').read_text())
subprocess.run(['python3', str(ROOT / '05_code/utilities/check_paths.py')], check=True, stdout=subprocess.DEVNULL)
target = ROOT / '08_manuscript/adversarial_revision_v27/candidate_frame_reconstruction.json'
assert not target.exists()
out = Path(cfg['outputs_root']) / 'diagnostics'
files = {'prior': out / 'efsa_diet_linkage/final_admission_status.csv',
         'scope': out / 'efsa_vegetable_scope_screen_20260920/primary_food_scope_screen.csv',
         'mapping': out / 'efsa_rpc_primo_bridge/rpc_mapping.csv',
         'ledger': ROOT / '10_submission/最终投稿材料_v26_文件夹版/01_Food_Control/tables/admission_decision_ledger.csv',
         'strict': ROOT / '10_submission/最终投稿材料_v26_文件夹版/01_Food_Control/tables/strict_37_ledger.csv'}
def read(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
country = {'BE':'Belgium','CY':'Cyprus','CZ':'Czechia','DE':'Germany','DK':'Denmark','ES':'Spain','FI':'Finland','FR':'France','GR':'Greece','HR':'Croatia','HU':'Hungary','IE':'Ireland','IT':'Italy','NL':'Netherlands','PL':'Poland','RO':'Romania'}
mapping = {r['source_residue_rpc']: r for r in read(files['mapping'])}
annexes = list((Path(cfg['raw_data_root']) / 'efsa_zenodo/13220663').glob('Annex D - *.xlsx'))
assert len(annexes) == 1
files['annex'] = annexes[0]
wb = openpyxl.load_workbook(files['annex'], read_only=True, data_only=True)
available = {(str(r[1]), str(r[3])) for r in wb['Table D.1 RPC Cons Chronic'].iter_rows(min_row=2, values_only=True) if r[1] and r[3] and r[5]}
wb.close()
prior = {(r['sampling_country_code'], r['rpc_code'], r['active_substance_code']): r for r in read(files['prior'])}
scope = {(r['sampling_country_code'], r['rpc_code'], r['active_substance_code']): r for r in read(files['scope']) if r['year']=='2022' and (r['food_scope_status']=='CANDIDATE_FOOD_SCOPE' or r['rpc_code']=='P0260040A')}
keys = {k for k, r in prior.items() if r['final_status']=='HOLD' and k in scope and (country.get(k[0],k[0]),mapping[k[1]]['official_primo_rpc']) in available}
ledger = read(files['ledger'])
saved = {(r['reporting_country'], r['rpc_code'], r['active_substance_code']) for r in ledger}
assert len(keys) == len(saved) == len(ledger) == 262 and keys == saved
strict = read(files['strict'])
assert len(strict) == 37 and all((r['reporting_country'], r['rpc_code'], r['active_substance_code']) in keys for r in strict)
assert all(r['year']=='2022' and int(r['sample_n'])>=10 and int(r['quantified_n'])>=3 for r in strict)
rec = {'candidate_count': len(keys), 'strict_ledger_count': len(strict), 'exact_membership_reconstruction': 'PASS',
       'candidate_foods': dict(Counter(r['vegetable'] for r in ledger)), 'candidate_markets': dict(Counter(r['reporting_country'] for r in ledger)),
       'strict_programmes': dict(Counter(r['programme'] for r in strict)), 'strict_commodity_codes': dict(Counter(r['rpc_code'] for r in strict)),
       'construction': 'Prior linkage HOLD keys intersected with the archived 2022 food-scope screen and same-reporting-country official PRIMo Annex D.1 chronic RPC row availability; not a census or a random sample of all EFSA cells. Observations were subsequently stratified by year/programme.',
       'boundary': 'Reconstruction of existing analytic selection, not a new exposure calculation or independent sample-level assay verification.',
       'input_hashes': {k: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in files.items()}}
target.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
print(json.dumps(rec, ensure_ascii=False, indent=2))
