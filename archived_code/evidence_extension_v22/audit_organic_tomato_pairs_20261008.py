"""Original-source paired concentration identification, never new exposure."""
import argparse,collections,csv,hashlib,io,json,zipfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
CFG={k.strip():json.loads(v.strip()) for l in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
     if l and not l.startswith('#') for k,v in [l.split(':',1)]}
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path(CFG['outputs_root'])/'diagnostics/organic_pair_identification_20261008')
OUT=ap.parse_args().out;OUT.mkdir(parents=True,exist_ok=False)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(name,x):
    with (OUT/name).open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False)
def write(name,x,fields=None):
    with (OUT/name).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(x[0]));w.writeheader();w.writerows(x)
def number(x):
    try:
        d=Decimal(x)
        return d if d.is_finite() else None
    except Exception:return None
def close(a,b):return abs(a-b)<=max(Decimal('1e-12'),abs(b)*Decimal('1e-10'))

freeze=json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text())
assert all(sha(Path(x['path']))==x['sha256'] for x in freeze['files'])
selected=read(Path(CFG['intermediate_data_root'])/'manuscript_data_reuse_audit_20261008/matched_frozen_chemical_pair_candidates.csv')
assert len(selected)==15
crosspath=Path(CFG['processed_data_root'])/'pesticide_residue_definition_crosswalk_20260921_v6.parquet'
cross={x['active_substance_code']:x for x in pq.read_table(crosspath).to_pylist()}
ready=read(Path(CFG['outputs_root'])/'diagnostics/efsa_scientific_exposure_admission/macp_37_execution_readiness_20260921_v6.csv')
baseline={x['active_substance_code']:x for x in ready if x['reporting_country']=='DE'}
targets={x['active_substance_code']:x for x in selected};lookup={}
for code in targets:
    for m in cross[code]['monitoring_definition_codes'].split('|'):
        assert m not in lookup or lookup[m]==code
        lookup[m]=code
rec=json.loads((ROOT/'00_admin/efsa_de_full_reconciliation_receipt_20261008.json').read_text())
src=next(x for x in rec['national_profiles'] if x['year']=='2022');archive=Path(src['path'])
before=sha(archive);assert before==src['sha256']
KEEP=['sampId_A','resId_A','paramCode.base.param','paramType','resType','resUnit','resVal','resLOQ','resLOD','exprResType',
      'sampMatCode.base.building','anMatCode.base.building','sampMatCode.prod','anMatCode.prod','sampMatCode.process','anMatCode.process',
      'sampCountry','origCountry','procCountry','sampY','sampM','sampD','progType','sampStrategy','progLegalRef','anPortSeq','evalLimitType',
      'labAccred','accredProc','resValRec','resValRecCorr','resInfo.notSummed']
records=collections.defaultdict(list);count=0
with zipfile.ZipFile(archive) as z:
    members=[x for x in z.infolist() if x.filename.lower().endswith('.csv')];assert len(members)==1
    member=members[0]
    with z.open(member) as binary,io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);header=next(reader);pos={k:header.index(k) for k in KEEP}
        codepos=pos['paramCode.base.param'];foodpos=pos['sampMatCode.base.building'];progpos=pos['progType'];strategypos=pos['sampStrategy']
        for line,values in enumerate(reader,2):
            count+=1
            if len(values)!=len(header):raise ValueError(('Malformed row',line))
            if values[codepos] in lookup and values[foodpos]=='A0DMX' and values[progpos]=='K009A' and values[strategypos]=='ST10A':
                code=lookup[values[codepos]]
                records[code].append({'active_code':code,'source_row':line,'member':member.filename,**{k:values[j] for k,j in pos.items()}})
            if count%1000000==0:print('Original DE2022 rows read',count,flush=True)
assert count==src['counts']['rows_scanned']==8026370
after=sha(archive);assert before==after
all_records=[r for k in targets for r in records[k]];write('source_measurement_rows.csv',all_records)
dump('source_definition_correspondence.json',[cross[k] for k in targets])

results=[];dispositions=[];audits=[];admitted_records=[]
for code,expected in targets.items():
    rows=records[code];rd=cross[code];ref=baseline[code];issues=[]
    if rd['status']!='RD_EXACT' or ref['residue_definition_status']!='RD_EXACT':issues.append('RISK_DEFINITION_NOT_EXACT')
    if len(rows)!=len({r['sampId_A'] for r in rows}):issues.append('MULTIPLE_MEASUREMENTS_PER_SAMPLE')
    if len(rows)!=len({r['resId_A'] for r in rows}):issues.append('REPEATED_RESULT_ID')
    if any(not r['sampId_A'] or not r['resId_A'] for r in rows):issues.append('MISSING_IDENTITY')
    for r in rows:
        if r['sampCountry']!='DE' or r['sampY']!='2022':issues.append('MARKET_OR_YEAR')
        if r['paramType']!='P005A':issues.append('NOT_DECLARED_COMPLETE_DEFINITION')
        if r['resUnit']!='G061A' or r['exprResType']!='B001A':issues.append('MASS_UNIT_OR_EXPRESSION')
        if r['evalLimitType']!='W002A':issues.append('LEGAL_REFERENCE_TYPE')
        if r['sampMatCode.prod'] not in ['A07SE','A0C6Y']:issues.append('UNKNOWN_PRODUCTION')
        if r['anPortSeq'] not in ['N_A','']:issues.append('ANALYTICAL_PORTION_REVIEW')
        if r['sampMatCode.process'] not in ['N_A',''] or r['anMatCode.process'] not in ['N_A','']:issues.append('EXPLICIT_PROCESSING_REVIEW')
        if r['resType']=='VAL':
            v=number(r['resVal']);q=number(r['resLOQ'])
            if v is None or v<0:issues.append('INVALID_QUANTIFIED_VALUE')
            if v is not None and q is not None and v<q:issues.append('VAL_BELOW_DECLARED_LOQ')
        elif r['resType']=='LOQ':
            q=number(r['resLOQ'])
            if q is None or q<=0:issues.append('MISSING_OR_INVALID_LOQ')
            if r['resVal'] not in ['','N_A']:issues.append('LOQ_WITH_VALUE_REQUIRES_REVIEW')
        else:issues.append('UNHANDLED_RESULT_TYPE')
    groups={label:[r for r in rows if r['sampMatCode.prod']==value] for label,value in [('organic','A07SE'),('nonorganic','A0C6Y')]}
    endpoints={}
    for label,group in groups.items():
        n=len(group);val=sum(r['resType']=='VAL' for r in group)
        if n!=int(expected[label+'_samples']) or val!=int(expected[label+'_val_samples']):issues.append('SUPPORT_TABLE_MISMATCH_'+label)
        if n<20:issues.append('PRESPECIFIED_SUPPORT_'+label)
        if not issues:
            low=sum((Decimal(r['resVal']) for r in group if r['resType']=='VAL'),Decimal(0))/n
            high=(sum((Decimal(r['resVal']) for r in group if r['resType']=='VAL'),Decimal(0))+
                  sum((Decimal(r['resLOQ']) for r in group if r['resType']=='LOQ'),Decimal(0)))/n
            # Different arithmetic expression using exact rational numbers.
            f_low=sum((Fraction(r['resVal']) if r['resType']=='VAL' else Fraction(0) for r in group),Fraction(0))/n
            f_high=sum((Fraction(r['resVal']) if r['resType']=='VAL' else Fraction(r['resLOQ']) for r in group),Fraction(0))/n
            assert close(low,Decimal(f_low.numerator)/Decimal(f_low.denominator)) and close(high,Decimal(f_high.numerator)/Decimal(f_high.denominator))
            endpoints[label]=(low,high,n,val)
    if not issues:
        total=sum(x[2] for x in endpoints.values())
        pooled_low=sum(x[0]*x[2] for x in endpoints.values())/total
        pooled_high=sum(x[1]*x[2] for x in endpoints.values())/total
        if total!=int(ref['sample_n']) or not close(pooled_low,Decimal(ref['monitoring_mean_lb_mg_kg'])) or not close(pooled_high,Decimal(ref['monitoring_mean_ub_mg_kg'])):
            issues.append('FROZEN_POOLED_ENDPOINT_RECONCILIATION')
    audits.append({'chemical':expected['pesticide_name'],'active_code':code,'measurement_rows':len(rows),
        'source_codes':'|'.join(sorted({r['paramCode.base.param'] for r in rows})),
        'source_categories':{k:dict(collections.Counter(r[k] for r in rows)) for k in KEEP if k not in ['sampId_A','resId_A','resVal','resLOQ','resLOD']},
        'issues':dict(collections.Counter(issues))})
    passed=not issues
    dispositions.append({'pesticide':expected['pesticide_name'],'active_code':code,'source_measurement_codes':rd['monitoring_definition_codes'],
        'status':'PASS_SOURCE_DECLARED_EXPRESSION_BOUNDS_ONLY' if passed else 'HOLD_NO_PAIRED_RESULT',
        'issues':'|'.join(sorted(set(issues))),'source_document':rd['source_document'],
        'laboratory_independent_validation':'NOT_PERFORMED','exposure_addition':0})
    if passed:
        lo,uo,no,vo=endpoints['organic'];ln,un,nn,vn=endpoints['nonorganic'];dl=lo-un;du=uo-ln
        direction='ORGANIC_LOWER_UNDER_CENSORING' if du<0 else 'NONORGANIC_LOWER_UNDER_CENSORING' if dl>0 else 'DIRECTION_UNRESOLVED'
        results.append({'pesticide':expected['pesticide_name'],'active_code':code,'organic_n':no,'nonorganic_n':nn,
            'organic_VAL':vo,'nonorganic_VAL':vn,'organic_LB_mg_kg':str(lo),'organic_UB_mg_kg':str(uo),
            'nonorganic_LB_mg_kg':str(ln),'nonorganic_UB_mg_kg':str(un),'difference_LB_mg_kg':str(dl),'difference_UB_mg_kg':str(du),
            'ratio_LB':str(lo/un) if ln>0 and un>0 else '', 'ratio_UB':str(uo/ln) if ln>0 else '',
            'direction':direction,'uncertainty':'CENSORING_ONLY_NOT_CI_NOT_CAUSAL','source_document':rd['source_document']})
        admitted_records.extend(rows)
write('candidate_dispositions.csv',dispositions)
write('paired_concentration_bounds.csv',results,['pesticide','active_code','organic_n','nonorganic_n','organic_VAL','nonorganic_VAL','organic_LB_mg_kg','organic_UB_mg_kg','nonorganic_LB_mg_kg','nonorganic_UB_mg_kg','difference_LB_mg_kg','difference_UB_mg_kg','ratio_LB','ratio_UB','direction','uncertainty','source_document'])
dump('source_gate_audit.json',audits)
dump('run_receipt.json',{'source_path':str(archive),'source_sha256_before':before,'source_sha256_after':after,'csv_rows_read':count,
    'zip_member':member.filename,'zip_member_crc_after_eof':'PASS','protocol_sha256':sha(ROOT/'01_protocol/organic_pair_partial_identification_20261008.md'),
    'crosswalk_sha256':sha(crosspath),'selected_candidates':15,'passed':len(results),'held':15-len(results),
    'directions':dict(collections.Counter(r['direction'] for r in results)),
    'distinct_selected_samples':len({r['sampId_A'] for r in all_records}),
    'source_rows_extracted':len(all_records),'exact_rational_endpoint_checks':len(results)*4,
    'frozen_hashes_before_and_after_pass':len(freeze['files']) if all(sha(Path(x['path']))==x['sha256'] for x in freeze['files']) else 0,
    'no_new_exposure_or_burden':True,'scope':'Sampled German2022 MACP tomato lots; source-declared expression and production; not causal organic effect or independent laboratory validation.'})
print(json.dumps({'passed':len(results),'held':15-len(results),'directions':dict(collections.Counter(r['direction'] for r in results))},ensure_ascii=False),flush=True)
