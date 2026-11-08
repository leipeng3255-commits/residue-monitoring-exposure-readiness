"""Retrospective interval-order and threshold diagnostics; no exposure modelling."""
import csv, hashlib, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
assert (ROOT/'00_admin/paths.yaml').is_file()
OUT=ROOT/'08_manuscript/panel_revision_v9/diagnostics'
OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'08_manuscript/final_food_control_version/revision_v6/tables'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return list(csv.DictReader((BASE/name).open()))
def write(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
def above(a,b):return a>b and not math.isclose(a,b,rel_tol=1e-12,abs_tol=0)
def bounds(intervals):
    return [(1+sum(above(l2,u) for j,(l2,u2) in enumerate(intervals) if j!=i),
             len(intervals)-sum(above(l,u2) for j,(l2,u2) in enumerate(intervals) if j!=i))
            for i,(l,u) in enumerate(intervals)]
assert bounds([(3,4),(1,2),(0,.5)])==[(1,1),(2,2),(3,3)]
assert bounds([(0,3),(1,4)])==[(1,2),(1,2)]
assert bounds([(1,1),(1,1)])==[(1,2),(1,2)]
cs=read('cell_diagnostics.csv');ss=read('strict_37_ledger.csv')
assert (len(cs),len(ss))==(19,37)
intervals=[(float(r['max_mean_percent_ADI_LB']),float(r['max_mean_percent_ADI_UB'])) for r in cs]
assert all(0<=l<=u for l,u in intervals)
rr=bounds(intervals);ranks=[];pairs=[]
for i,r in enumerate(cs):
    ranks.append({'unit':r['occurrence_country']+' '+r['pesticide'],'mean_LB_max_percent_ADI':intervals[i][0],
                  'mean_UB_max_percent_ADI':intervals[i][1],'earliest_rank_outer_bound':rr[i][0],
                  'latest_rank_outer_bound':rr[i][1],'interpretation':'DISPLAYED_CONTRIBUTION_ORDER_NOT_DISEASE_RISK'})
    for j in range(i+1,len(cs)):
        li,ui=intervals[i];lj,uj=intervals[j]
        state='I_ABOVE_J' if above(li,uj) else 'J_ABOVE_I' if above(lj,ui) else 'UNRESOLVED_OVERLAP_OR_TOUCH'
        pairs.append({'unit_i':ranks[i]['unit'],'unit_j':cs[j]['occurrence_country']+' '+cs[j]['pesticide'],'interval_order':state})
assert len(pairs)==171
grid=[]
for n in [10,25,50,100]:
    for q in [0,1,3,5,10]:
        rows=[r for r in ss if int(r['sample_n'])>=n and int(r['quantified_n'])>=q]
        admitted=[r for r in rows if r['residue_definition_status'] in ['RD_EXACT','RD_CONVERSION_AVAILABLE']]
        grid.append({'minimum_samples':n,'minimum_quantified_results':q,'strict_units_retained':len(rows),'current_chemical_subset_retained':len(admitted),'original_support_setting':n==10 and q==3})
original=next(r for r in grid if r['original_support_setting'])
assert original['strict_units_retained']==37 and original['current_chemical_subset_retained']==19
write('interval_rank_bounds.csv',ranks);write('pairwise_interval_order.csv',pairs);write('support_threshold_grid.csv',grid)
receipt={'protocol_sha256':sha(ROOT/'01_protocol/post_freeze_priority_diagnostics_v9.md'),
    'input_sha256':{x:sha(BASE/x) for x in ['cell_diagnostics.csv','strict_37_ledger.csv']},
    'pairs':len(pairs),'guaranteed_order_pairs':sum(r['interval_order']!='UNRESOLVED_OVERLAP_OR_TOUCH' for r in pairs),
    'unresolved_pairs':sum(r['interval_order']=='UNRESOLVED_OVERLAP_OR_TOUCH' for r in pairs),
    'units_not_ruled_out_for_first_rank':[r['unit'] for r in ranks if r['earliest_rank_outer_bound']==1],
    'fixed_rank_units':sum(r['earliest_rank_outer_bound']==r['latest_rank_outer_bound'] for r in ranks),
    'abamectin_rank_bounds':next(r for r in ranks if r['unit']=='DE abamectin'),
    'support_grid':grid,'synthetic_algorithm_checks':3,'new_exposure_calculations':0,
    'interpretation':'Outer rank bounds, not probability or proof of joint attainability; no risk-priority claim'}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='support_grid'},indent=2))
