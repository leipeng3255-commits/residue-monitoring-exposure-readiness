"""Hand-specified artificial bounds: Decimal replay versus rational arithmetic."""
import argparse,json,hashlib
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'01_protocol/controlled_numeric_cases_v21.json'

def decimal_bound(c):
    rows=c['rows']
    if not c['complete_expression']:return None,'CHEMICAL'
    if len(rows)!=c['denominator'] or c['denominator']<=0:return None,'DENOMINATOR'
    if len({r['id'] for r in rows})!=len(rows):return None,'IDENTIFIERS'
    lb=Decimal(0);ub=Decimal(0)
    for r in rows:
        if r['unit'] not in ('mg/kg','ug/kg'):return None,'UNITS'
        scale=Decimal(1) if r['unit']=='mg/kg' else Decimal('0.001')
        if r['flag']=='VAL':
            if r['value'] is None or r['value']<0:return None,'VALUE'
            lb+=Decimal(str(r['value']))*scale;ub+=Decimal(str(r['value']))*scale
        elif r['flag'] in ('LOD','LOQ'):
            if r['limit'] is None or r['limit']<=0:return None,'LIMIT'
            ub+=Decimal(str(r['limit']))*scale
        else:return None,'CENSORING'
    return [lb/len(rows)*Decimal(str(c['factor'])),ub/len(rows)*Decimal(str(c['factor']))],None

def rational_bound(c):
    # Does not call the Decimal implementation; uses distinct exact fractions.
    if c['complete_expression'] is False:return None,'CHEMICAL'
    n=c['denominator'];records=c['rows']
    if n!=len(records) or n<1:return None,'DENOMINATOR'
    ids=[x['id'] for x in records]
    if len(set(ids))!=n:return None,'IDENTIFIERS'
    endpoints=[]
    for x in records:
        scales={'mg/kg':Fraction(1),'ug/kg':Fraction(1,1000)}
        if x['unit'] not in scales:return None,'UNITS'
        if x['flag'] in ['LOD','LOQ']:
            if not isinstance(x['limit'],(int,float)) or x['limit']<=0:return None,'LIMIT'
            endpoints.append((Fraction(0),Fraction(str(x['limit']))*scales[x['unit']]))
        elif x['flag']=='VAL':
            if not isinstance(x['value'],(int,float)) or x['value']<0:return None,'VALUE'
            v=Fraction(str(x['value']))*scales[x['unit']];endpoints.append((v,v))
        else:return None,'CENSORING'
    return [sum(pair[i] for pair in endpoints)*Fraction(str(c['factor']))/n for i in (0,1)],None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'00_admin/verification_extension_v21')
    output=parser.parse_args().out;output.mkdir(exist_ok=True,parents=True)
    spec=json.loads(SPEC.read_text());result=[]
    for c in spec['cases']:
        a,ar=decimal_bound(c);b,br=rational_bound(c);expected=c['expected']
        passed=(ar==br==c.get('reason'))
        if expected is not None:
            passed &= all(abs(x-Decimal(str(y.numerator))/Decimal(str(y.denominator)))<Decimal('1e-25') and
                abs(x-Decimal(e))<Decimal('1e-25') for x,y,e in zip(a,b,expected))
        else:passed &= a is None and b is None
        result.append({'id':c['id'],'Decimal':None if a is None else list(map(str,a)),
                       'rational':None if b is None else list(map(str,b)),'reason':ar,'pass':bool(passed)})
    out={'spec_sha256':hashlib.sha256(SPEC.read_bytes()).hexdigest(),'cases':result,'failures':[x['id'] for x in result if not x['pass']],
         'boundary':'Nine disclosed artificial fixtures. Exact fractions and Decimal checks do not establish real-programme classification accuracy.'}
    with (output/'controlled_numeric_first_run.json').open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps({'numeric_cases':len(result),'failures':out['failures']}));assert not out['failures']
if __name__=='__main__':main()
