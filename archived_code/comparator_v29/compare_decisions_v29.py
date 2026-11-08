"""Same-evidence comparator plus labelled component stress tests; no new exposure."""
import collections,csv,hashlib,importlib.util,json,sys
from decimal import Decimal,InvalidOperation
from fractions import Fraction
from pathlib import Path
from datetime import datetime,timezone
import yaml
ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
BASE=ROOT/'10_submission/最终投稿材料_v28_预设来源检验_文件夹版/03_可复现数据与代码_NOT_DIRECT_UPLOAD'
WORK=ROOT/'08_manuscript/comparator_v29'
OUT=Path(cfg['intermediate_data_root'])/'comparator_v29_20261013'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

# No prediction function may inspect expected labels or expected endpoint columns.
def baseline(x):
    if x.get('target_supported',True) is not True:return {'label':'HOLD_TARGET_INCOMPATIBLE'}
    kind=x['source_kind']
    if kind=='EAT2_UNANALYSED':return {'label':'HOLD_UNANALYSED'}
    if kind=='FDA_POLICY_UNVERIFIED':return {'label':'HOLD_SOURCE_POLICY'}
    try:
        if kind=='EATI':
            if x['qualifier']=='VAL':lo=hi=Fraction(x['value'])
            elif x['qualifier']=='<LD':lo,hi=Fraction(0),Fraction(x['lod'])
            elif x['qualifier']=='<LQ':lo,hi=Fraction(0),Fraction(x['loq'])
            else:return {'label':'HOLD_SOURCE_POLICY'}
        else:lo,hi=Fraction(x['lower']),Fraction(x['upper'])
        cut=Fraction(x.get('threshold','0'))
    except (TypeError,ValueError,ZeroDivisionError):return {'label':'HOLD_INVALID_INTERVAL'}
    if hi<lo:return {'label':'HOLD_REVERSED_BOUNDS'}
    if x['mode']=='interval':return {'label':'INTERVAL_SUPPORTED','lower':str(lo),'upper':str(hi)}
    if x['mode']=='reference':
        answers=set()
        if lo<=cut:answers.add('NO_EXCEEDANCE_WITHIN_BOUNDS')
        if hi>cut:answers.add('EXCEEDANCE_WITHIN_BOUNDS')
    else:
        answers=set()
        if lo<cut:answers.add('BELOW')
        if hi>cut:answers.add('ABOVE')
        if lo<=cut<=hi:answers.add('POINT_MATCH_ONLY')
    return {'label':next(iter(answers)) if len(answers)==1 else 'CENSORING_UNRESOLVED'}

def framework(x,arm='FRAMEWORK'):
    if arm!='IGNORE_TARGET' and x.get('target_supported',True) is not True:
        return {'label':'HOLD_TARGET_INCOMPATIBLE'}
    kind=x['source_kind']
    try:
        if arm=='NUMERIC_ONLY' and kind in ('EATI','EAT2_UNANALYSED','FDA_POLICY_UNVERIFIED'):
            if x.get('value') is None:return {'label':'HOLD_NO_NUMERIC_VALUE'}
            lower=upper=Decimal(x['value'])
        elif kind=='EAT2_UNANALYSED':return {'label':'HOLD_UNANALYSED'}
        elif kind=='FDA_POLICY_UNVERIFIED':return {'label':'HOLD_SOURCE_POLICY'}
        elif kind=='EATI':
            states={'VAL':(x.get('value'),x.get('value')),'<LD':('0',x.get('lod')),'<LQ':('0',x.get('loq'))}
            if x['qualifier'] not in states:return {'label':'HOLD_SOURCE_POLICY'}
            lower,upper=map(Decimal,states[x['qualifier']])
        else:lower,upper=Decimal(x['lower']),Decimal(x['upper'])
        if not lower.is_finite() or not upper.is_finite():return {'label':'HOLD_INVALID_INTERVAL'}
    except (InvalidOperation,TypeError,ValueError):return {'label':'HOLD_INVALID_INTERVAL'}
    if lower>upper:return {'label':'HOLD_REVERSED_BOUNDS'}
    if arm=='ZERO_WIDTH_ONLY' and lower!=upper:return {'label':'HOLD_NONPOINT'}
    if x['mode']=='interval':return {'label':'INTERVAL_SUPPORTED','lower':str(lower),'upper':str(upper)}
    # The original v23 function is executed unchanged, not replaced by baseline().
    return {'label':v23.direct({'lower':str(lower),'upper':str(upper),'threshold':x['threshold'],'mode':x['mode'],'compatible':True})}

def classify(got,case):
    exp=case['expected'];label=got['label']
    want_decisive=not (exp.startswith('HOLD') or exp=='CENSORING_UNRESOLVED')
    got_decisive=not (label.startswith('HOLD') or label=='CENSORING_UNRESOLVED')
    wrong_endpoint=False
    if exp==label=='INTERVAL_SUPPORTED':
        wrong_endpoint=[Fraction(got[k]) for k in ['lower','upper']] != [Fraction(z) for z in case['expected_bounds']]
    return dict(exact_reference_match=int(label==exp and not wrong_endpoint),unsupported_permission=int(got_decisive and not want_decisive),unnecessary_withholding=int(want_decisive and not got_decisive),wrong_definitive_label=int(want_decisive and got_decisive and label!=exp),wrong_numeric_endpoint=int(wrong_endpoint))

if __name__=='__main__':
    assert Path(cfg['raw_data_root']).is_dir()
    commit=json.loads((WORK/'commitment.json').read_text())
    assert sha(WORK/'cases.json')==commit['cases_sha256']
    assert sha(ROOT/'01_protocol/comparator_audit_v29_20261013.md')==commit['plan_sha256']
    for p,h in commit['input_hashes'].items():assert sha(BASE/p)==h,p
    module=BASE/'question_rules_v23/question_interval_audit_v23.py'
    assert sha(module)==commit['framework_sha256']
    spec=importlib.util.spec_from_file_location('frozen_v23',module);v23=importlib.util.module_from_spec(spec);spec.loader.exec_module(v23)
    cases=json.loads((WORK/'cases.json').read_text());OUT.mkdir(exist_ok=False)
    # Strip reference labels from all prediction inputs to avoid accidental leakage.
    results=[];mismatches=[]
    for c in cases:
        x={k:v for k,v in c.items() if not k.startswith('expected') and k not in ('basis','source')}
        predictions={'DIRECT_GUIDANCE':baseline(x)}|{a:framework(x,a) for a in ['FRAMEWORK','NUMERIC_ONLY','ZERO_WIDTH_ONLY','IGNORE_TARGET']}
        if predictions['DIRECT_GUIDANCE']['label']!=predictions['FRAMEWORK']['label']:mismatches.append(c['case_id'])
        for arm,p in predictions.items():
            results.append(dict(case_id=c['case_id'],family=c['family'],arm=arm,expected=c['expected'],result=p['label'],lower=p.get('lower',''),upper=p.get('upper',''),**classify(p,c),source=c['source']))
    def write(name,rows):
        with (OUT/name).open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write('case_results.csv',results)
    summary=[]
    metrics=['exact_reference_match','unsupported_permission','unnecessary_withholding','wrong_definitive_label','wrong_numeric_endpoint']
    for family in dict.fromkeys(c['family'] for c in cases):
        for arm in ['DIRECT_GUIDANCE','FRAMEWORK','NUMERIC_ONLY','ZERO_WIDTH_ONLY','IGNORE_TARGET']:
            rr=[r for r in results if r['family']==family and r['arm']==arm]
            summary.append(dict(family=family,arm=arm,n=len(rr),**{m:sum(r[m] for r in rr) for m in metrics}))
    write('family_summary.csv',summary)
    fail=[r for r in results if r['arm'] in ['DIRECT_GUIDANCE','FRAMEWORK'] and not r['exact_reference_match']]
    receipt={'time_UTC':datetime.now(timezone.utc).isoformat(),'case_count':len(cases),'case_families':dict(collections.Counter(c['family'] for c in cases)),'code_sha256':sha(Path(__file__)),'commitment_sha256':sha(WORK/'commitment.json'),'fair_arm_label_disagreements':mismatches,'fair_arm_reference_discrepancies':fail,'status':'PASS' if not fail and not mismatches else 'DISCREPANCY','independent_gold_standard':False,'human_performance_measured':False,'superiority':'NOT_DEMONSTRATED','interpretation':'Finite internal conformance and controlled component omission; not representative usual practice, prospective accuracy or statistical equivalence. Source-interval adapter new in v29; original v23 numeric core unchanged.','outputs':{name:sha(OUT/name) for name in ['case_results.csv','family_summary.csv']}}
    (OUT/'first_run_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps([r for r in summary if r['unsupported_permission'] or r['unnecessary_withholding'] or r['wrong_numeric_endpoint']],indent=2))
    assert receipt['status']=='PASS','First-run discrepancies saved; diagnose without overwriting.'
