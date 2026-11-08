"""Two separate rule implementations tested against prospectively saved fixtures."""
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT/'01_protocol/controlled_evidence_cases_v21.json'
OUT = ROOT/'00_admin/verification_extension_v21'

def prerequisites(r):
    reasons = set()
    if r['denominator'] <= 0 or r['denominator'] != r['record_count'] or r['positive_only']: reasons.add('DENOMINATOR')
    if not r['unique_keys']: reasons.add('IDENTIFIERS')
    if r['unit'] not in ('mg/kg','ug/kg'): reasons.add('UNITS')
    if r['limit'] is None or r['limit'] <= 0: reasons.add('LIMIT')
    if not r['censoring_known']: reasons.add('CENSORING')
    concentration = not reasons
    if not r['definition_complete']: reasons.add('CHEMICAL')
    if r['conversion_required'] and not r['conversion_documented']: reasons.add('CONVERSION')
    if r['food_form'] != r['target_form']: reasons.add('FOOD_FORM')
    if not r['diet_link']: reasons.add('DIET')
    if r['model_mean'] is None or r['model_mean'] < 0: reasons.add('MODEL_INPUT')
    if r['ADI'] is None or r['ADI'] <= 0: reasons.add('REFERENCE_VALUE')
    if not r['model_path_documented']: reasons.add('MODEL_PATH')
    exposure = not reasons
    if not r['population_frame']: reasons.add('POPULATION')
    if not r['period_compatible']: reasons.add('PERIOD')
    return [concentration, exposure, not reasons], sorted(reasons)

def dimensions(r):
    # Separately expressed dimension rules; never calls prerequisites.
    checks = {
        'DENOMINATOR': r['record_count'] == r['denominator'] and r['denominator'] > 0 and r['positive_only'] is False,
        'IDENTIFIERS': r['unique_keys'] is True,
        'UNITS': r['unit'] in ['ug/kg','mg/kg'],
        'LIMIT': isinstance(r['limit'], (int,float)) and r['limit'] > 0,
        'CENSORING': r['censoring_known'] is True,
        'CHEMICAL': r['definition_complete'] is True,
        'CONVERSION': not r['conversion_required'] or r['conversion_documented'],
        'FOOD_FORM': r['target_form'] == r['food_form'],
        'DIET': r['diet_link'] is True,
        'MODEL_INPUT': isinstance(r['model_mean'], (int,float)) and r['model_mean'] >= 0,
        'REFERENCE_VALUE': isinstance(r['ADI'], (int,float)) and r['ADI'] > 0,
        'MODEL_PATH': r['model_path_documented'] is True,
        'POPULATION': r['population_frame'] is True,
        'PERIOD': r['period_compatible'] is True,
    }
    analytical = ['DENOMINATOR','IDENTIFIERS','UNITS','LIMIT','CENSORING']
    scenario = analytical + ['CHEMICAL','CONVERSION','FOOD_FORM','DIET','MODEL_INPUT','REFERENCE_VALUE','MODEL_PATH']
    population = scenario + ['POPULATION','PERIOD']
    return [all(checks[k] for k in group) for group in [analytical,scenario,population]], sorted(k for k,v in checks.items() if not v)

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT)
    OUT=parser.parse_args().out
    spec = json.loads(SPEC.read_text()); cases = []; failures = []; invariance = []
    for case in spec['cases']:
        row = spec['baseline'] | case['change']; expected = (case['expected'], sorted(case['reasons']))
        a,b = prerequisites(row),dimensions(row)
        good = a == b == expected
        cases.append({'id':case['id'],'expected':expected,'prerequisite':a,'dimension':b,'pass':good})
        if not good: failures.append(case['id'])
        variants = [dict(reversed(list(row.items()))), row | {'sample_id':'renamed_001'}]
        if row['unit'] == 'mg/kg':
            variants.append(row | {'unit':'ug/kg','limit':None if row['limit'] is None else row['limit']*1000,
                                   'model_mean':None if row['model_mean'] is None else row['model_mean']*1000})
        for i,v in enumerate(variants):
            passed = prerequisites(v) == a and dimensions(v) == b
            invariance.append({'case':case['id'],'variant':i,'pass':passed})
    result = {'spec_sha256':hashlib.sha256(SPEC.read_bytes()).hexdigest(),'cases':cases,'case_count':len(cases),
        'case_failures':failures,'invariance_tests':invariance,'invariance_count':len(invariance),
        'invariance_failures':sum(not x['pass'] for x in invariance),
        'boundary':'Author-defined artificial fixtures and two internal implementations, not independent human validation or accuracy on real programmes.',
        'unit_boundary':'Unit test checks gate invariance with jointly scaled input/limit, not a new exposure calculation.'}
    OUT.mkdir(exist_ok=True)
    with (OUT/'controlled_case_first_run.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ['case_count','case_failures','invariance_count','invariance_failures']}))
    assert not failures and not result['invariance_failures']
if __name__ == '__main__': main()
