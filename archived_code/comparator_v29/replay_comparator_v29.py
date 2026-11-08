"""Portable same-evidence replay from a delivered comparator_v29 directory."""
import argparse,ast,csv,hashlib,json,types
from decimal import Decimal,InvalidOperation
from fractions import Fraction
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def functions_from(path,names,scope):
    source=path.read_text()
    for node in ast.parse(source).body:
        if isinstance(node,ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    assert all(n in scope for n in names)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parent.parent);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    common=args.package;payload=common/'comparator_v29'
    commit=json.loads((payload/'commitment.json').read_text());first=json.loads((payload/'first_run_receipt.json').read_text())
    assert sha(payload/'cases.json')==commit['cases_sha256']
    assert sha(payload/'compare_decisions_v29.py')==first['code_sha256']
    assert sha(common/'question_rules_v23/question_interval_audit_v23.py')==commit['framework_sha256']
    for p,h in commit['input_hashes'].items():assert sha(common/p)==h,p
    scope={'Decimal':Decimal,'InvalidOperation':InvalidOperation,'Fraction':Fraction}
    functions_from(common/'question_rules_v23/question_interval_audit_v23.py',['direct'],scope)
    scope['v23']=types.SimpleNamespace(direct=scope['direct'])
    functions_from(payload/'compare_decisions_v29.py',['baseline','framework','classify'],scope)
    cases=json.loads((payload/'cases.json').read_text());results=[]
    for c in cases:
        x={k:v for k,v in c.items() if not k.startswith('expected') and k not in ('basis','source')}
        pred={'DIRECT_GUIDANCE':scope['baseline'](x)}|{a:scope['framework'](x,a) for a in ['FRAMEWORK','NUMERIC_ONLY','ZERO_WIDTH_ONLY','IGNORE_TARGET']}
        for arm,p in pred.items():
            results.append(dict(case_id=c['case_id'],family=c['family'],arm=arm,expected=c['expected'],result=p['label'],lower=p.get('lower',''),upper=p.get('upper',''),**scope['classify'](p,c),source=c['source']))
    args.out.mkdir(parents=True,exist_ok=False)
    path=args.out/'case_results.csv'
    with path.open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    receipt={'case_arm_rows':len(results),'case_results_sha256':sha(path),'byte_identical_to_first_run':sha(path)==first['outputs']['case_results.csv'],'new_exposure':False,'independent_human_validation':False}
    (args.out/'replay_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2));assert receipt['byte_identical_to_first_run']
