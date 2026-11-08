"""Internal question-rule verification on synthetic cases and preserved outputs."""
import argparse,collections,csv,hashlib,json
from decimal import Decimal,InvalidOperation
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def direct(r):
    if not r.get('compatible',True):return 'HOLD_TARGET_INCOMPATIBLE'
    try:
        l,u,t=[Decimal(x) for x in [r['lower'],r['upper'],r['threshold']]]
        if not all(x.is_finite() for x in [l,u,t]):return 'HOLD_INVALID_INTERVAL'
    except (InvalidOperation,TypeError,ValueError):return 'HOLD_INVALID_INTERVAL'
    if l>u:return 'HOLD_REVERSED_BOUNDS'
    if r['mode']=='reference':
        return 'NO_EXCEEDANCE_WITHIN_BOUNDS' if u<=t else 'EXCEEDANCE_WITHIN_BOUNDS' if l>t else 'CENSORING_UNRESOLVED'
    assert r['mode']=='order'
    return 'ABOVE' if l>t else 'BELOW' if u<t else 'POINT_MATCH_ONLY' if l==u==t else 'CENSORING_UNRESOLVED'
def possible_answers(r):
    # Separate possible-answer enumeration; does not call direct().
    if r.get('compatible',True) is False:return 'HOLD_TARGET_INCOMPATIBLE'
    try:l,u,t=[Fraction(x) for x in [r['lower'],r['upper'],r['threshold']]]
    except (ValueError,TypeError,ZeroDivisionError):return 'HOLD_INVALID_INTERVAL'
    if u<l:return 'HOLD_REVERSED_BOUNDS'
    if r['mode']=='reference':
        yes=u>t;no=l<=t
        if yes and no:return 'CENSORING_UNRESOLVED'
        return 'EXCEEDANCE_WITHIN_BOUNDS' if yes else 'NO_EXCEEDANCE_WITHIN_BOUNDS'
    assert r['mode']=='order'
    options={k for k,v in [('BELOW',l<t),('POINT_MATCH_ONLY',l<=t<=u),('ABOVE',u>t)] if v}
    return next(iter(options)) if len(options)==1 else 'CENSORING_UNRESOLVED'

def run(package,out,spec):
    cfg={k.strip():v.strip() for l in (package/'paths.yaml').read_text().splitlines() if l and not l.startswith('#') for k,v in [l.split(':',1)]}
    tables=package/cfg['tables'];out.mkdir(parents=True,exist_ok=False)
    cases=json.loads(spec.read_text());tested=[];invariance=[];failures=[]
    for r in cases['cases']:
        a,b=direct(r),possible_answers(r);good=a==b==r['expected']
        tested.append({'id':r['id'],'expected':r['expected'],'direct':a,'rational':b,'pass':good})
        if not good:failures.append(r['id'])
        try:
            scaled=r|{k:str(Decimal(r[k])*1000) for k in ['lower','upper','threshold']}
            if all(Decimal(r[k]).is_finite() for k in ['lower','upper','threshold']):
                ok=direct(scaled)==possible_answers(scaled)==a
                invariance.append({'id':r['id'],'positive_unit_scale_1000':ok})
                if not ok:failures.append(r['id']+'_scale')
        except (InvalidOperation,TypeError,ValueError):pass
    cellpath=tables/'cell_diagnostics.csv';ratiopath=tables/'same_chemical_ratio_bounds.csv'
    pairpath=package/'evidence_extension_v22/paired_concentration_bounds.csv'
    cells=read(cellpath);ratios=read(ratiopath);pairs=read(pairpath)
    assert (len(cells),len(ratios),len(pairs))==(19,3,15)
    actual=[]
    for r in cells:
        x={'mode':'reference','lower':r['max_mean_percent_ADI_LB'],'upper':r['max_mean_percent_ADI_UB'],'threshold':'100'}
        a,b=direct(x),possible_answers(x);assert a==b=='NO_EXCEEDANCE_WITHIN_BOUNDS'
        actual.append({'question_family':'single_food_mean_reference','id':r['occurrence_country']+'|'+r['pesticide'],**x,'outcome':a})
    for r in ratios:
        x={'mode':'order','lower':r['ratio_lower'],'upper':r['ratio_upper'],'threshold':'1'}
        a,b=direct(x),possible_answers(x);assert a==b
        actual.append({'question_family':'same_chemical_CZ_DE_order','id':r['pesticide'],**x,'outcome':a})
    for r in pairs:
        x={'mode':'order','lower':r['difference_LB_mg_kg'],'upper':r['difference_UB_mg_kg'],'threshold':'0'}
        a,b=direct(x),possible_answers(x);assert a==b=='CENSORING_UNRESOLVED'
        actual.append({'question_family':'selected_production_group_order','id':r['pesticide'],**x,'outcome':a})
    assert collections.Counter(r['outcome'] for r in actual if r['question_family']=='same_chemical_CZ_DE_order')=={'ABOVE':2,'CENSORING_UNRESOLVED':1}
    with (out/'empirical_question_outcomes.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(actual[0]));w.writeheader();w.writerows(actual)
    receipt={'spec_sha256':sha(spec),'artificial_fixture_count':len(tested),'first_run_cases':tested,
      'positive_unit_invariance_count':len(invariance),'invariance':invariance,'failures':failures,
      'question_families':{family:dict(collections.Counter(r['outcome'] for r in actual if r['question_family']==family)) for family in dict.fromkeys(r['question_family'] for r in actual)},
      'input_hashes':{str(p.relative_to(package)):sha(p) for p in [cellpath,ratiopath,pairpath]},
      'interpretation':'Question-specific censoring answer checks; not new exposure, source validation, independent human evaluation, population inference or an overall readiness rate.',
      'outputs':[{'name':'empirical_question_outcomes.csv','sha256':sha(out/'empirical_question_outcomes.csv')}],
      'code_sha256':sha(Path(__file__))}
    with (out/'interval_rule_first_run.json').open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({k:receipt[k] for k in ['artificial_fixture_count','positive_unit_invariance_count','failures','question_families']}))
    assert not failures

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path);ap.add_argument('--out',type=Path);ap.add_argument('--spec',type=Path)
    args=ap.parse_args()
    if args.package is None:
        cfg={k.strip():json.loads(v.strip()) for l in (ROOT/'00_admin/paths.yaml').read_text().splitlines() if l and not l.startswith('#') for k,v in [l.split(':',1)]}
        assert Path(cfg['data_root']).is_dir()
        package=ROOT/'10_submission/最终投稿材料_v22_文件夹版/01_Food_Control'
        out=args.out or Path(cfg['outputs_root'])/'diagnostics/question_interval_v23_20261009'
        spec=args.spec or ROOT/'01_protocol/question_interval_cases_v23.json'
    else:
        package=args.package;out=args.out
        assert out is not None,'Use a fresh output directory'
        spec=args.spec or package/'question_rules_v23/question_interval_cases_v23.json'
    run(package,out,spec)
