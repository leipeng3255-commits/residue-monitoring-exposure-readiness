"""Check the domain of the median factor separately from positive endpoint ratios."""
import csv,hashlib,json,subprocess
from fractions import Fraction
from decimal import Decimal
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
subprocess.run(['python3',str(ROOT/'05_code/utilities/check_paths.py')],check=True,stdout=subprocess.DEVNULL)
p=Path(cfg['intermediate_data_root'])/'tds_semantics_challenge_20261013/eat2_chemical_denominator_bounds.csv'
rows=list(csv.DictReader(p.open()));assert len(rows)==322
def median(xs):
    xs=sorted(xs);return (xs[(len(xs)-1)//2]+xs[len(xs)//2])/2
out={'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'boundary':'Algebraic denominator diagnostic, not exposure or population mean; positive LB and UB have different eligibility sets','endpoint_domains':{}}
for key in ['LB_tested','UB_tested']:
    rr=[r for r in rows if Decimal(r[key])>0]
    m=median([Fraction(int(r['n_tested']),1193) for r in rr])
    # Validate every stored positive wrong endpoint, with disclosed decimal-rounding tolerance.
    wrong='WRONG_LB_all_rows' if key.startswith('LB') else 'WRONG_UB_all_rows'
    for r in rr:
        factor=Decimal(r['n_tested'])/1193
        assert abs(Decimal(r[wrong])-Decimal(r[key])*factor)<Decimal('1e-24')
    out['endpoint_domains'][key]={'positive_columns':len(rr),'zero_columns':322-len(rr),'exact_median_factor':str(m),'decimal_median':float(m)}
assert out['endpoint_domains']['LB_tested']['positive_columns']==58
assert out['endpoint_domains']['UB_tested']['positive_columns']==322
assert out['endpoint_domains']['LB_tested']['exact_median_factor']=='683/1193'
assert out['endpoint_domains']['UB_tested']['exact_median_factor']=='410/1193'
out['verification']='Exact integer/Fraction median; all stored endpoint identities within absolute 1e-24 source-decimal rounding'
target=ROOT/'08_manuscript/tds_eight_panel_v26/source_reassessment/endpoint_domain_verification.json'
with target.open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
