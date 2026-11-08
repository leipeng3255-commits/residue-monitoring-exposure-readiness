#!/usr/bin/env python3
"""Validate native matched azoxystrobin exports, preserve auditable pilot table."""
import argparse,csv,hashlib,json,math
from pathlib import Path
import openpyxl,pyarrow as pa,pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
P={k.strip():Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
   if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
a=argparse.ArgumentParser();a.add_argument('--country',required=True);args=a.parse_args()
d=P['outputs_root']/'diagnostics/primo_scientific_runs'
occ=list(csv.DictReader((P['outputs_root']/'diagnostics/efsa_scientific_exposure_admission/macp_occurrence_lbub.csv').open()))
o=next(x for x in occ if x['reporting_country']==args.country and x['active_substance_code']=='RF-0035-001-PPP')
def read(p):
    w=openpyxl.load_workbook(p,read_only=True,data_only=True);s=w.active;s.reset_dimensions();v=list(s.values);w.close()
    return [dict(zip(v[0],x)) for x in v[1:]]
data={b:read(d/f'{args.country}_2022_tomato_azoxystrobin_{b}_20260921_detailed.xlsx') for b in ['LB','UB']}
assert len(data['LB'])==len(data['UB'])==88
ratio=float(o['monitoring_mean_ub_mg_kg'])/float(o['monitoring_mean_lb_mg_kg'])
result=[]
for lo,hi in zip(data['LB'],data['UB']):
    for k in ['Popclass','Country','Survey','N subjects','HRP Comment']:assert lo[k]==hi[k]
    for k in ['Mean Exposure (µg/kg bw per day)','Mean exposure % ADI','HRP (µg/kg bw per day)','HRP (% ADI)','Exposure Chronic P95 (µg/kg bw per day)','P95 (% ADI)']:
        if lo[k] is None: assert hi[k] is None;continue
        assert hi[k]>=lo[k]>=0
        assert math.isclose(hi[k],lo[k]*ratio,rel_tol=1e-10,abs_tol=1e-12),(k,lo[k],hi[k],ratio)
    row={'occurrence_country':args.country,'survey_country':lo['Country'],'survey':lo['Survey'],'population_group':lo['Popclass'],
         'survey_n':lo['N subjects'],'year':2022,'commodity':'tomato','pesticide':'azoxystrobin','programme':'EU_MACP_RANDOM',
         'sample_n':int(o['sample_n']),'quantified_n':int(o['quantified_n']),'occurrence_LB_mg_kg':float(o['monitoring_mean_lb_mg_kg']),
         'occurrence_UB_mg_kg':float(o['monitoring_mean_ub_mg_kg']),'ADI_EFSA_mg_kg_bw_day':0.2,'ADI_JMPR2024_sensitivity':0.03,
         'RD_status':'RD_EXACT','PF_status':'PF_NOT_REQUIRED_FOR_RAW_RPC_EQUIVALENT_ESTIMAND','HRP_percentile':lo['HRP Comment'],
         'qc':'PASS_WITH_LIMITATION','limitation':'Single raw-tomato contribution; transported occurrence; historical consumption; not total diet; ADI authority differs'}
    for b,x in [('LB',lo),('UB',hi)]:
        row[f'exposure_mean_{b}_ug_kg_bw_day']=x['Mean Exposure (µg/kg bw per day)']
        row[f'percent_ADI_mean_{b}']=x['Mean exposure % ADI']
        row[f'percent_ADI_HRP_{b}']=x['HRP (% ADI)']
        row[f'percent_JMPR_ADI_mean_{b}']=x['Mean exposure % ADI']*.2/.03
    result.append(row)
target=P['processed_data_root']/f'chronic_exposure_pilot_{args.country}_azoxystrobin_20260921.parquet'
if not target.exists():pq.write_table(pa.Table.from_pylist(result),target)
else:assert pq.read_table(target).to_pylist()==result
report={'status':'PASS_WITH_LIMITATION','paired_strata':88,'native_output_pair':'LB and UB independently uploaded/calculated/downloaded',
        'concentration_ratio':ratio,'LB_UB_order':'PASS','linear_ratio_check':'PASS','dataset':str(target),
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'max_mean_percent_ADI_UB':max(x['percent_ADI_mean_UB'] for x in result),
        'max_HRP_percent_ADI_UB':max(x['percent_ADI_HRP_UB'] for x in result),
        'warning':'Not a whole-project analysis freeze. HRP percentiles differ by stratum. No disease inference.'}
t=d/f'{args.country}_azoxystrobin_pair_qc_20260921.json'
if not t.exists():
    with t.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
