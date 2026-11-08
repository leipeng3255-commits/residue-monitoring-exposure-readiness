"""Resolve specified source expressions; retain the initial all-HOLD audit."""
import collections,csv,hashlib,json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CFG={k.strip():json.loads(v.strip()) for l in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
     if l and not l.startswith('#') for k,v in [l.split(':',1)]}
BASE=Path(CFG['outputs_root'])/'diagnostics/organic_pair_identification_20261008'
OUT=Path(CFG['outputs_root'])/'diagnostics/organic_pair_gate_resolution_20261008'
OUT.mkdir(exist_ok=False)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(n,x):
    with (OUT/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def write(n,x,fields=None):
    with (OUT/n).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(x[0]));w.writeheader();w.writerows(x)
def num(x):
    try:
        v=Decimal(x);return v if v.is_finite() else None
    except Exception:return None
def close(a,b):return abs(a-b)<=max(Decimal('1e-12'),abs(b)*Decimal('1e-10'))
def dec(x):return Decimal(x.numerator)/Decimal(x.denominator)
freeze=json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text())
assert len(freeze['files'])==95 and all(sha(Path(x['path']))==x['sha256'] for x in freeze['files'])
first=json.loads((BASE/'run_receipt.json').read_text());archive=Path(first['source_path'])
assert first['passed']==0 and first['held']==15 and first['csv_rows_read']==8026370
assert first['zip_member_crc_after_eof']=='PASS'
assert sha(archive)==first['source_sha256_before']==first['source_sha256_after']
extract=BASE/'source_measurement_rows.csv';extract_sha=sha(extract);allrows=read(extract)
assert len(allrows)==first['source_rows_extracted']
crosspath=Path(CFG['processed_data_root'])/'pesticide_residue_definition_crosswalk_20260921_v6.parquet'
assert sha(crosspath)==first['crosswalk_sha256']
cross={r['active_substance_code']:r for r in json.loads((BASE/'source_definition_correspondence.json').read_text())}
selection=Path(CFG['intermediate_data_root'])/'manuscript_data_reuse_audit_20261008/matched_frozen_chemical_pair_candidates.csv'
selected=read(selection);assert len(selected)==15
baseline={r['active_substance_code']:r for r in read(Path(CFG['outputs_root'])/'diagnostics/efsa_scientific_exposure_admission/macp_37_execution_readiness_20260921_v6.csv') if r['reporting_country']=='DE'}
complete=[r for r in allrows if r['paramType']=='P005A']
components=[r for r in allrows if r['paramType']!='P005A']
write('retained_complete_expression_rows.csv',complete)
write('separate_component_rows.csv',components)
metadata=['sampCountry','origCountry','sampY','sampM','sampD','sampMatCode.prod','sampMatCode.base.building','sampMatCode.process']
byid=collections.defaultdict(list)
for r in complete:byid[r['sampId_A']].append(r)
conflicts={s:[k for k in metadata if len({r[k] for r in rows})>1] for s,rows in byid.items()}
conflicts={s:k for s,k in conflicts.items() if k}
dump('cross_chemical_metadata_conflicts.json',conflicts)
results=[];dispositions=[];audits=[];checks=0
for expected in selected:
    code=expected['active_substance_code'];rd=cross[code];ref=baseline[code]
    rows=[r for r in complete if r['active_code']==code];issues=[]
    if rd['status']!='RD_EXACT' or ref['residue_definition_status']!='RD_EXACT':issues.append('DEFINITION_HOLD')
    if len({r['sampId_A'] for r in rows})!=len(rows) or len({r['resId_A'] for r in rows})!=len(rows):issues.append('REPEATED_ID')
    for r in rows:
        if not r['sampId_A'] or not r['resId_A'] or r['sampId_A'] in conflicts:issues.append('IDENTITY_OR_METADATA_CONFLICT')
        if r['sampCountry']!='DE' or r['sampY']!='2022' or r['progType']!='K009A' or r['sampStrategy']!='ST10A':issues.append('FRAME')
        if r['sampMatCode.base.building']!='A0DMX' or r['anMatCode.base.building']!='A0DMX':issues.append('COMMODITY')
        if r['sampMatCode.prod'] not in ['A07SE','A0C6Y'] or r['sampMatCode.prod']!=r['anMatCode.prod']:issues.append('PRODUCTION')
        if r['sampMatCode.process'] not in ['A0C0S','N_A',''] or r['sampMatCode.process']!=r['anMatCode.process']:issues.append('PROCESS')
        if r['resUnit']!='G061A' or r['exprResType']!='B001A' or r['evalLimitType']!='W002A':issues.append('UNIT_OR_EXPRESSION')
        if r['anPortSeq'] not in ['N_A','']:issues.append('PORTION')
        if r['resType']=='VAL':
            v,q=num(r['resVal']),num(r['resLOQ'])
            if v is None or v<0 or (q is not None and v<q):issues.append('QUANTIFIED_VALUE')
        elif r['resType']=='LOQ':
            q=num(r['resLOQ'])
            if q is None or q<=0 or r['resVal'] not in ['','N_A']:issues.append('CENSORING_LIMIT')
        else:issues.append('RESULT_TYPE')
    groups={k:[r for r in rows if r['sampMatCode.prod']==p] for k,p in [('organic','A07SE'),('nonorganic','A0C6Y')]}
    for k,g in groups.items():
        if len(g)!=int(expected[k+'_samples']) or sum(r['resType']=='VAL' for r in g)!=int(expected[k+'_val_samples']) or len(g)<20:issues.append('DENOMINATOR_'+k)
    endpoints={};fractions={}
    if not issues:
        for k,g in groups.items():
            n=len(g)
            l=sum((Decimal(r['resVal']) if r['resType']=='VAL' else Decimal(0) for r in g),Decimal(0))/n
            u=sum((Decimal(r['resVal']) if r['resType']=='VAL' else Decimal(r['resLOQ']) for r in g),Decimal(0))/n
            fl=sum((Fraction(r['resVal']) if r['resType']=='VAL' else Fraction(0) for r in g),Fraction(0))/n
            fu=sum((Fraction(r['resVal']) if r['resType']=='VAL' else Fraction(r['resLOQ']) for r in g),Fraction(0))/n
            assert close(l,dec(fl)) and close(u,dec(fu));checks+=2
            endpoints[k]=(l,u);fractions[k]=(fl,fu)
        n=len(rows)
        for j,field in [(0,'monitoring_mean_lb_mg_kg'),(1,'monitoring_mean_ub_mg_kg')]:
            pooled=sum(endpoints[k][j]*len(g) for k,g in groups.items())/n
            if n!=int(ref['sample_n']) or not close(pooled,Decimal(ref[field])):issues.append('FROZEN_ENDPOINT_'+field)
    passed=not issues
    audits.append({'pesticide':expected['pesticide_name'],'n_complete':len(rows),'issues':dict(collections.Counter(issues)),
        'processing':dict(collections.Counter(r['sampMatCode.process'] for r in rows)),
        'source_codes':dict(collections.Counter(r['paramCode.base.param'] for r in rows)),
        'lab_accreditation':dict(collections.Counter(r['labAccred'] for r in rows))})
    dispositions.append({'pesticide':expected['pesticide_name'],'active_code':code,'status':'COMPLETE_EXPRESSION_CONCENTRATION_BOUNDS_ONLY' if passed else 'HOLD',
        'issues':'|'.join(sorted(set(issues))),'initial_disposition':'HOLD_RETAINED','new_exposure':0})
    if passed:
        lo,uo=endpoints['organic'];ln,un=endpoints['nonorganic'];flo,fuo=fractions['organic'];fln,fun=fractions['nonorganic']
        dl,du=lo-un,uo-ln
        assert close(dl,dec(flo-fun)) and close(du,dec(fuo-fln));checks+=2
        rl,ru=(lo/un,uo/ln) if ln>0 else (None,None)
        if rl is not None:assert close(rl,dec(flo/fun)) and close(ru,dec(fuo/fln));checks+=2
        results.append({'pesticide':expected['pesticide_name'],'active_code':code,'organic_n':len(groups['organic']),'nonorganic_n':len(groups['nonorganic']),
            'organic_VAL':sum(r['resType']=='VAL' for r in groups['organic']),'nonorganic_VAL':sum(r['resType']=='VAL' for r in groups['nonorganic']),
            'organic_LB_mg_kg':str(lo),'organic_UB_mg_kg':str(uo),'nonorganic_LB_mg_kg':str(ln),'nonorganic_UB_mg_kg':str(un),
            'difference_LB_mg_kg':str(dl),'difference_UB_mg_kg':str(du),'ratio_LB':'' if rl is None else str(rl),'ratio_UB':'' if ru is None else str(ru),
            'direction':'ORGANIC_LOWER_UNDER_CENSORING' if du<0 else 'NONORGANIC_LOWER_UNDER_CENSORING' if dl>0 else 'DIRECTION_UNRESOLVED',
            'interval_type':'CENSORING_BOUNDS_NOT_CI','source_scope':'DE_2022_MACP_TOMATO_RPC','causal_coefficient':'NOT_IDENTIFIED'})
write('candidate_dispositions.csv',dispositions);write('paired_concentration_bounds.csv',results)
dump('source_gate_audit.json',audits)
unique=[v[0] for v in byid.values()]
balance=[]
for field in ['origCountry','sampM','sampMatCode.process']:
    for (prod,value),n in sorted(collections.Counter((r['sampMatCode.prod'],r[field]) for r in unique).items()):
        balance.append({'field':field,'production_code':prod,'value':value,'distinct_samples':n})
write('shared_sample_metadata_balance.csv',balance)
assert sha(archive)==first['source_sha256_before'] and sha(extract)==extract_sha
assert all(sha(Path(x['path']))==x['sha256'] for x in freeze['files'])
receipt={'first_pass_retained':str(BASE),'source_path':str(archive),'source_sha256':first['source_sha256_before'],
    'source_full_csv_rows_verified_in_first_pass':first['csv_rows_read'],'extraction_sha256':extract_sha,
    'protocol_sha256':sha(ROOT/'01_protocol/organic_pair_gate_resolution_20261008.md'),'selection_sha256':sha(selection),
    'selected':15,'passed':len(results),'held':15-len(results),'complete_expression_rows':len(complete),
    'separate_component_rows':len(components),'distinct_samples':len(unique),'production_distinct_samples':dict(collections.Counter(r['sampMatCode.prod'] for r in unique)),
    'cross_chemical_metadata_conflicts':len(conflicts),'directions':dict(collections.Counter(r['direction'] for r in results)),
    'finite_ratio_intervals':sum(r['ratio_UB']!='' for r in results),'exact_rational_comparisons':checks,
    'frozen_sha256_pass':95,'new_exposure_units':0,'independent_human_validation':False,
    'outputs':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file()]}
dump('run_receipt.json',receipt)
print(json.dumps({k:receipt[k] for k in ['passed','held','distinct_samples','directions','finite_ratio_intervals','exact_rational_comparisons']},ensure_ascii=False))
