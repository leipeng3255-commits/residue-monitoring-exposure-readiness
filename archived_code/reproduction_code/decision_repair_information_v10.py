"""Target-conditioned re-audit and explicitly hypothetical information scenarios."""
import csv, gzip, hashlib, json, math
from collections import Counter, defaultdict
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
P = yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT = ROOT/'08_manuscript/decision_revision_v10'
OUT.mkdir(exist_ok=True)
T = OUT/'tables'; T.mkdir(exist_ok=True)
BASE = ROOT/'08_manuscript/final_food_control_version/revision_v9_panel_edit/tables'
D = Path(P['outputs_root'])/'diagnostics/efsa_scientific_exposure_admission'
inputs = {}
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    inputs[str(p)] = sha(p)
    with p.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def save(name, rows):
    p=T/name
    if p.exists(): assert list(csv.DictReader(p.open())) == [{k:str(v) for k,v in r.items()} for r in rows], p
    else:
        with p.open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
def dump(name,data):
    p=OUT/name; text=json.dumps(data,indent=2,ensure_ascii=False)+'\n'
    if p.exists(): assert p.read_text()==text,p
    else: p.write_text(text)
freeze_path=ROOT/'00_admin/analysis_freeze_manifest_20260921.json'
freeze=json.loads(freeze_path.read_text())
assert all(sha(r['path'])==r['sha256'] for r in freeze['files'])
strict=read(BASE/'strict_37_ledger.csv'); cells=read(BASE/'cell_diagnostics.csv')
admission=read(BASE/'admission_decision_ledger.csv')
assert (len(strict),len(cells),len(admission))==(37,19,262)
cellmap={(r['occurrence_country'],r['pesticide'].casefold()):r for r in cells}
audit=[]
for r in strict:
    chemical_name=r['active_substance'].casefold()
    # Explicit historical synonym; never fuzzy-match chemical expressions.
    if chemical_name=='chlorantraniliprole (dpx e-2y45)': chemical_name='chlorantraniliprole'
    key=(r['reporting_country'],chemical_name); c=cellmap.get(key)
    chemistry=r['residue_definition_status']
    approved=chemistry in ('RD_EXACT','RD_CONVERSION_AVAILABLE')
    assert approved == (c is not None)
    assert r['loq_complete']=='YES'
    if approved:
        lower,upper=float(c['occurrence_LB']),float(c['occurrence_UB'])
        route='ANALYTICAL_REFINEMENT_FOR_INFORMATION; TARGET_COMPATIBLE_DIET_AND_SAMPLING_FOR_POPULATION'
        next_evidence='Lower limits or directly quantified censored values; compatible contemporary diet and sampling frame for a new population target'
    else:
        lower,upper=float(r['monitoring_mean_lb_mg_kg']),float(r['monitoring_mean_ub_mg_kg'])
        route='COMPATIBLE_CHEMICAL_EXPRESSION_EVIDENCE' if chemistry=='RD_MISMATCH_NO_CONVERSION' else 'SOURCE_CODE_AND_CROP_SPECIFIC_DEFINITION_VERIFICATION'
        next_evidence='Measured full risk definition or authoritative compatible conversion; may require additional analytical components' if chemistry=='RD_MISMATCH_NO_CONVERSION' else 'Source component mapping and crop/treatment-specific definition or conversion; outcome of verification unknown'
    audit.append({'unit':r['reporting_country']+' '+r['active_substance'],
        'frame':'37_SELECTED_STRICT_MACP_CANDIDATES', 'original_RD_status':chemistry,
        'recorded_samples':r['sample_n'],'recorded_quantified':r['quantified_n'],
        'numeric_censor_limits':'DOCUMENTED_COMPLETE',
        'chemical_sample_aggregate_validation':'SUPPORTED_FOR_SAVED_APPLICATION' if approved else 'UNKNOWN_NOT_RELEASED',
        'native_paired_output':'VERIFIED_SAVED_PAIR' if approved else 'NOT_RELEASED',
        'historical_raw_RPC_scenario':'SUPPORTED_WITH_DOCUMENTED_ADAPTATION' if approved else 'HOLD_CHEMISTRY',
        'information_width_basis':'RISK_COMPATIBLE_SAVED_MEAN' if approved else 'MONITORED_EXPRESSION_ONLY',
        'lower_mean':lower,'upper_mean':upper,'nonzero_censor_width':upper>lower,
        'fixed_displayed_rank':'NO' if approved else 'NOT_EVALUATED',
        'contemporary_population_exposure':'NOT_ESTABLISHED',
        'repair_routes':route,'next_evidence':next_evidence,
        'successful_future_repair':'UNKNOWN',
        'decision_changed':'NO'})
save('target_conditioned_audit_37.csv',audit)

# Ideal remeasurement: calculate all deterministic allocations, not favourable cases only.
ordered=sorted(cells,key=lambda r:r['occurrence_country']+' '+r['pesticide'])
allocations={'ZERO':lambda i:0.,'LOW_005':lambda i:.05,'MID_025':lambda i:.25,
             'HIGH_075':lambda i:.75,'HETEROGENEOUS':lambda i:[.05,.25,.75][i%3]}
rates=[1.,.5,.2,.1]
summary=[]; detail=[]; previous={}
def separated(a,b):
    return (a[0]>b[1] and not math.isclose(a[0],b[1],rel_tol=1e-12)) or (b[0]>a[1] and not math.isclose(b[0],a[1],rel_tol=1e-12))
for name,allocation in allocations.items():
    prior_pairs=0
    for rate in rates:
        intervals=[]; widths=[]
        for i,c in enumerate(ordered):
            l,u=float(c['occurrence_LB']),float(c['occurrence_UB']); w=u-l
            k=float(c['max_mean_percent_ADI_UB'])/u
            assert math.isclose(k*l,float(c['max_mean_percent_ADI_LB']),rel_tol=1e-9,abs_tol=1e-12)
            theta=allocation(i)
            nl,nu=(l,l+rate*w) if theta<rate else (l+theta*w,l+theta*w)
            assert l-1e-12<=nl<=nu<=u+1e-12
            assert nu-nl<=rate*w+1e-12
            unit=c['occurrence_country']+' '+c['pesticide']; old=previous.get((name,unit))
            if old: assert nl>=old[0]-1e-12 and nu<=old[1]+1e-12
            previous[(name,unit)]=(nl,nu)
            if rate==1: assert math.isclose(nl,l) and math.isclose(nu,u)
            intervals.append((k*nl,k*nu)); widths.append((nu-nl)/w)
            detail.append({'allocation':name,'limit_ratio_r':rate,'unit':unit,'theta_assumed':theta,
                'hypothetical_concentration_lower':nl,'hypothetical_concentration_upper':nu,
                'hypothetical_displayed_scale_lower':k*nl,'hypothetical_displayed_scale_upper':k*nu,
                'remaining_width_fraction':(nu-nl)/w,
                'status':'HYPOTHETICAL_NOT_OBSERVED_NOT_NATIVE_PRIMO_OUTPUT'})
        n=sum(separated(intervals[i],intervals[j]) for i in range(19) for j in range(i+1,19))
        assert n>=prior_pairs; prior_pairs=n
        if rate==1: assert n==92
        summary.append({'allocation':name,'limit_ratio_r':rate,'separated_pairs':n,'unresolved_pairs':171-n,
            'maximum_remaining_width_fraction':max(widths),'pair_denominator':171,
            'status':'DETERMINISTIC_STRESS_SCENARIO_NOT_PREDICTION'})
save('information_scenario_units.csv',detail); save('information_scenario_summary.csv',summary)

# Real all-nondetect example; no new exposure endpoint.
occ=read(D/'macp_occurrence_lbub.csv')
nd=[r for r in occ if r['year']=='2022' and r['reporting_country']=='DE' and r['rpc_code']=='P0231010A'
    and int(r['sample_n'])>=10 and int(r['quantified_n'])==0 and r['loq_complete']=='YES' and r['duplicate_conflict_n']=='0']
assert len(nd)==2 and {r['active_substance_code'] for r in nd}=={'RF-0104-001-PPP','RF-0268-001-PPP'}
meta=read(D/'programme_classification.csv')
wanted={r['active_substance_code'] for r in nd}
selected={(r['sample_id'],r['active_substance_code']):r for r in meta if r['year']=='2022' and r['reporting_country']=='DE' and r['rpc_code']=='P0231010A' and r['active_substance_code'] in wanted and r['programme_class']=='EU_MACP_RANDOM'}
obs=Path(P['intermediate_data_root'])/'efsa_2022_2024_sample_level_candidates_20260914T111235/candidate_sample_level_observations.csv.gz'
inputs[str(obs)]=sha(obs); records=defaultdict(list)
with gzip.open(obs,'rt',newline='') as f:
    for r in csv.DictReader(f):
        if r['year']=='2022' and r['sampling_country_code']=='DE' and r['rpc_code']=='P0231010A' and (r['sample_id'],r['active_substance_code']) in selected:
            records[r['active_substance_code']].append(r)
examples=[]; sample_records=[]
for r in nd:
    code=r['active_substance_code']; rr=records[code]
    assert len(rr)==len({x['sample_id'] for x in rr})==214
    assert all(x['result_type']=='LOQ' and x['censor_limit_available']=='YES' and x['duplicate_conflict_flag']=='NO' and x['res_unit_code']=='G061A' for x in rr)
    lower=sum(float(x['censor_lower_mg_kg']) for x in rr)/214
    upper=sum(float(x['censor_upper_mg_kg']) for x in rr)/214
    assert lower==0 and math.isclose(upper,float(r['monitoring_mean_ub_mg_kg']),rel_tol=1e-12)
    a=next(x for x in admission if x['reporting_country']=='DE' and x['rpc_code']=='P0231010A' and x['active_substance_code']==code)
    codes=sorted({x['residue_definition_codes'] for x in rr})
    limits=[float(x['censor_upper_mg_kg']) for x in rr]
    examples.append({'chemical':a['pesticide'],'active_substance_code':code,'source_definition_codes':'|'.join(codes),
        'programme':'2022_DE_MACP_RAW_TOMATO','sample_n':214,'quantified_n':0,'complete_limits':True,
        'monitored_mean_lower_mg_kg':lower,'monitored_mean_upper_mg_kg':upper,
        'minimum_reported_limit_mg_kg':min(limits),'maximum_reported_limit_mg_kg':max(limits),
        'limited_target':'MONITORED_EXPRESSION_CONCENTRATION_INTERVAL',
        'chemical_documentary_evidence':'FRUIT_CROP_PARENT_DEFINITION_SUPPORTED_EFSA_2018_2023' if code=='RF-0268-001-PPP' else 'TARGET_SPECIFIC_RISK_DEFINITION_NOT_ADJUDICATED',
        'laboratory_full_expression_validation':'NOT_CERTIFIED',
        'new_exposure_admission':'HOLD_NO_NATIVE_PRIMO_CALCULATION',
        'original_disposition':a['current_classification'],
        'definition_source':'https://doi.org/10.2903/j.efsa.2018.5284' if code=='RF-0268-001-PPP' else 'NONE_ADJUDICATED'})
    sample_records.extend({'chemical':a['pesticide'],'sample_id':x['sample_id'],'source_definition_codes':x['residue_definition_codes'],
        'result_type':x['result_type'],'limit_mg_kg':x['censor_upper_mg_kg'],
        'source_archive':x['source_archive'],'source_record_id':x['source_record_id']} for x in rr)
save('all_nondetect_examples.csv',examples); save('all_nondetect_sample_audit.csv',sample_records)
# Pin exactly the archives underlying these examples, read-only.
for path in {x['source_archive'] for x in sample_records}:
    assert Path(path).is_relative_to(Path(P['raw_data_root']))
    inputs[path]=sha(path)
receipt={'protocol_sha256':sha(ROOT/'01_protocol/decision_repair_information_protocol_v10.md'),
    'freeze_files_verified':len(freeze['files']),'input_sha256':inputs,
    'audit_rows':len(audit),'chemical_decisions':dict(Counter(x['original_RD_status'] for x in audit)),
    'admitted_units_with_nonzero_censor_width':sum(x['nonzero_censor_width'] and x['native_paired_output']=='VERIFIED_SAVED_PAIR' for x in audit),
    'information_scenarios':summary,'all_nondetect_examples':examples,
    'native_PRIMo_runs':0,'new_empirical_exposure_units':0,
    'validation':'Frozen hashes; input hashes; scenario recovery, nesting, width and ordering checks; 428 unique audited sample-chemical records. Investigator-conducted, not independent validation.'}
assert all(sha(path)==h for path,h in inputs.items())
dump('analysis_receipt.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k not in ('input_sha256','information_scenarios')},indent=2))
