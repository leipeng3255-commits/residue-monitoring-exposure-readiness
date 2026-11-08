"""Freeze known, source-traceable task cases before executing the new comparator."""
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
assert Path(cfg['data_root']).is_dir()
BASE=ROOT/'10_submission/最终投稿材料_v28_预设来源检验_文件夹版'
COMMON=BASE/'03_可复现数据与代码_NOT_DIRECT_UPLOAD'
WORK=ROOT/'08_manuscript/comparator_v29'
WORK.mkdir(exist_ok=True)
assert not (WORK/'commitment.json').exists()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
inputs=[COMMON/'tables/cell_diagnostics.csv',COMMON/'tables/same_chemical_ratio_bounds.csv',COMMON/'evidence_extension_v22/paired_concentration_bounds.csv',COMMON/'source_reassessment/eati_source_interval_examples.csv',COMMON/'tables/all_nondetect_examples.csv',COMMON/'source_transport_v28/source_profile_first_run.json',COMMON/'question_rules_v23/question_interval_cases_v23.json',COMMON/'question_rules_v23/empirical_question_outcomes.csv']
for p in inputs: assert p.exists(),p
old=read(inputs[-1]);cases=[]
for r in old:
    cases.append(dict(case_id='REAL|'+r['question_family']+'|'+r['id'],family=r['question_family'],mode=r['mode'],lower=r['lower'],upper=r['upper'],threshold=r['threshold'],target_supported=True,source_kind='saved_interval',expected=r['outcome'],basis='Previously saved endpoints and explicit strict predicate; mathematical reference, not independent adjudication.',source='question_rules_v23/empirical_question_outcomes.csv#'+r['id']))
for r in read(inputs[3]):
    cases.append(dict(case_id='EATI|'+r['source_row'],family='known_source_examples',mode='interval',source_kind='EATI',value=r['primary_lower'] if r['type_res']=='VAL' else None,qualifier=r['type_res'],lod=r['ld'],loq=r['lq'],target_supported=True,expected='INTERVAL_SUPPORTED',expected_bounds=[r['primary_lower'],r['primary_upper']],basis='EATi source type and limits; declared conservative substitution policy, not exact concentration truth.',source='source_reassessment/eati_source_interval_examples.csv#row='+r['source_row']))
cases.append(dict(case_id='EAT2|blank_format',family='known_source_examples',mode='interval',source_kind='EAT2_UNANALYSED',value=None,target_supported=True,expected='HOLD_UNANALYSED',basis='A LIRE B11: a blank is not analysed; format fixture, not a new sampled row.',source='source_reassessment/source_instruction_anchors.csv#EAT2'))
p=json.loads(inputs[5].read_text())
# Preserve the two already published source-coordinate examples; no favourable selection.
for label,value,lod,loq,coord in [('Non-Detect','0','1.1','3.7','2018!A2:T2'),('Detect','2','1.1','3.7','2018!A1589:T1589')]:
    cases.append(dict(case_id='FDA|'+label,family='known_source_examples',mode='interval',source_kind='FDA_POLICY_UNVERIFIED',value=value,qualifier=label,lod=lod,loq=loq,target_supported=True,expected='HOLD_SOURCE_POLICY',basis='The exported qualifier/value does not establish the final TDSi endpoint policy. Approximate LOD is display context, not used for interval calculation.',source='source_transport_v28/source_profile_first_run.json#'+coord))
for r in read(inputs[4]):
    cases.append(dict(case_id='DE_ALL_BQL|'+r['chemical'],family='known_source_examples',mode='interval',source_kind='saved_interval',lower=r['monitored_mean_lower_mg_kg'],upper=r['monitored_mean_upper_mg_kg'],target_supported=True,expected='INTERVAL_SUPPORTED',expected_bounds=[r['monitored_mean_lower_mg_kg'],r['monitored_mean_upper_mg_kg']],basis='Complete analyte-specific tested denominator and LOQ bounds support the monitored-expression interval only, not new exposure.',source='tables/all_nondetect_examples.csv#'+r['chemical']))
for r in list(cases):
    if r['family']=='single_food_mean_reference':
        cases.append(r|dict(case_id=r['case_id'].replace('REAL|','RETARGET|'),family='retargeted_current_population',target_supported=False,expected='HOLD_TARGET_INCOMPATIBLE',basis='Same historical endpoints; target changed to unconditional contemporary population claim without verified diet/supply transport. Paired target challenge, not new empirical data.'))
for r in json.loads(inputs[6].read_text())['cases']:
    cases.append(r|dict(case_id='ARTIFICIAL|'+r['id'],family='artificial_boundaries',target_supported=r.get('compatible',True),source_kind='saved_interval',source='question_rules_v23/question_interval_cases_v23.json#'+r['id'],basis='Declared artificial strict-boundary/invalid-input case; not an empirical observation.'))
assert len(cases)==90 and len({r['case_id'] for r in cases})==90,len(cases)
(WORK/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
plan=ROOT/'01_protocol/comparator_audit_v29_20261013.md'
commit={'time_UTC':datetime.now(timezone.utc).isoformat(),'prior_knowledge':'All underlying evidence and broad outcomes previously known. Not unseen validation or public preregistration.','case_count':len(cases),'plan_sha256':sha(plan),'cases_sha256':sha(WORK/'cases.json'),'input_hashes':{str(x.relative_to(COMMON)):sha(x) for x in inputs},'framework_sha256':sha(COMMON/'question_rules_v23/question_interval_audit_v23.py'),'v28_manifest_sha256':sha(BASE/'file_manifest.json')}
(WORK/'commitment.json').write_text(json.dumps(commit,ensure_ascii=False,indent=2))
print(json.dumps(commit,ensure_ascii=False,indent=2))
