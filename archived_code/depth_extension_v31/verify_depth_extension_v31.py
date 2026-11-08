"""Alternate Decimal row-deletion replay from extracted source fields, not endpoints."""
from decimal import Decimal as D, getcontext
from pathlib import Path
import csv,json,hashlib,math,collections as C
import yaml
getcontext().prec=50
ROOT=Path(__file__).resolve().parents[2];cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(cfg['intermediate_data_root'])/'depth_extension_v31_20261014'
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def eq(a,b):assert math.isclose(float(a),float(b),rel_tol=2e-12,abs_tol=1e-14),(a,b)
def decimal_fraction(s):
    a,*b=s.split('/');return D(a)/D(b[0]) if b else D(a)
sources=json.loads((OUT/'extraction_receipt.json').read_text());raw=[]
for s in sources:
    p=OUT/s['extract'];assert sha(p)==s['extract_sha256'];raw.extend(read(p))
binding=read(OUT/'source_bindings.csv');saved=read(OUT/'reconstructed_19_lot_rows.csv')
summaries={r['unit_id']:r for r in read(OUT/'all19_influence_summary.csv')}
deletes={(r['unit_id'],r['omitted_sample_id']):r for r in read(OUT/'all19_single_lot_deletions.csv')}
ratios={(r['pesticide'],r['omitted_market'],r['omitted_sample_id']):r for r in read(OUT/'shared_ratio_deletions.csv')}
groups={};nchecked=0
for b in binding:
    unit=b['unit_id'];market=unit.split('|')[0];codes=b['monitoring_codes'].split('|');factor=decimal_fraction(b['factor'])
    rr=[r for r in raw if r['sampCountry']==market and r['paramCode.base.param'] in codes and r['paramType']=='P005A']
    aa=[r for r in saved if r['unit_id']==unit]
    assert len(rr)==len(aa)==len({r['sampId_A'] for r in rr})==len({r['resId_A'] for r in rr})
    assert {(r['sampId_A'],r['resId_A']) for r in rr}=={(r['sample_id'],r['result_id']) for r in aa}
    rr=sorted(rr,key=lambda r:r['sampId_A']);s=summaries[unit]
    assert len(rr)==int(s['n']) and sum(r['resType']=='VAL' for r in rr)==int(s['quantified_n'])
    eq(factor,s['factor'])
    def means(rs):
        return tuple(factor*sum((D(r['resVal']) if r['resType']=='VAL' else D(0) if k=='lower' else D(r['resLOQ'])) for r in rs)/D(len(rs)) for k in ('lower','upper'))
    lo,hi=means(rr);eq(lo,s['lower']);eq(hi,s['upper'])
    groups[(market,s['pesticide'])]=(rr,means(rr))
    for r in rr:
        a,b=means([q for q in rr if q['sampId_A']!=r['sampId_A']]);v=deletes[(unit,r['sampId_A'])]
        eq(a,v['lower']);eq(b,v['upper']);eq(a/lo,v['lower_relative']);eq(b/hi,v['upper_relative']);nchecked+=1
assert nchecked==len(deletes)
for (name,market,omitted),s in ratios.items():
    means={}
    for m in ('CZ','DE'):
        rr=[r for r in groups[(m,name)][0] if not (m==market and r['sampId_A']==omitted)]
        means[m]=(sum(D(r['resVal']) if r['resType']=='VAL' else D(0) for r in rr)/len(rr),
                  sum(D(r['resVal']) if r['resType']=='VAL' else D(r['resLOQ']) for r in rr)/len(rr))
    a,b=means['CZ'][0]/means['DE'][1],means['CZ'][1]/means['DE'][0]
    eq(a,s['lower']);eq(b,s['upper'])
    result='CZ_ABOVE_DE' if a>1 else 'CZ_BELOW_DE' if b<1 else 'UNRESOLVED'
    assert result==s['decision']
    a0,b0=groups[('CZ',name)][1],groups[('DE',name)][1]
    eq(a0[0]/b0[1],s['original_lower']);eq(a0[1]/b0[0],s['original_upper'])
inventory=read(OUT/'all_declared_code_inventory.csv')
rawcounts=C.Counter((r['sampCountry'],r['paramCode.base.param'],r['paramType']) for r in raw)
assert len(rawcounts)==len(inventory) and sum(rawcounts.values())==len(raw)
for i in inventory:assert rawcounts[(i['market'],i['monitoring_code'],i['parameter_type'])]==int(i['rows'])
old=read(Path(cfg['outputs_root'])/'diagnostics/organic_pair_gate_resolution_20261008/retained_complete_expression_rows.csv')
old_de={}
for r in old:old_de.setdefault(r['active_code'],set()).add((r['sampId_A'],r['resId_A']))
checked_historical=0
for b in binding:
    unit=b['unit_id'];market,*_,active=unit.split('|')
    if market=='DE' and active in old_de:
        assert {(r['sample_id'],r['result_id']) for r in saved if r['unit_id']==unit}==old_de[active]
        checked_historical+=1
assert checked_historical==15
report=dict(status='PASS',independent_implementation_not_independent_investigator=True,
    original_units_reconciled=19,keyed_lot_deletions_compared=nchecked,keyed_ratio_deletions_compared=len(ratios),
    all_inventory_units_count_reconciled=len(inventory),raw_scoped_rows=len(raw),
    exact_ID_sets_against_prior_15_DE_extract=checked_historical,
    CZ_and_converted_identity_boundary='Raw reconstruction checked against mapped codes, source keys, historical counts/means; no historical frozen per-lot manifest claimed.',
    new_exposure=0,code_sha256=sha(Path(__file__)))
with (OUT/'verification_receipt.json').open('x') as h:json.dump(report,h,indent=2)
print(json.dumps(report,indent=2))
