#!/usr/bin/env python3
"""Validate only completed native pairs; never fabricate missing exports."""
import argparse,csv,hashlib,json,math
from pathlib import Path
import openpyxl,pyarrow as pa,pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
P={k.strip():Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
   if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
d=P['outputs_root']/'diagnostics/primo_scientific_runs'
def read(p):
 w=openpyxl.load_workbook(p,read_only=True,data_only=True);s=w.active;s.reset_dimensions();v=list(s.values);w.close();return [dict(zip(v[0],r)) for r in v[1:]]
def key(x):return (x['Popclass'],x['Country'],x['Survey'])
baseline={key(x):x for x in read(d/'CZ_2022_tomato_azoxystrobin_LB_20260921_detailed.xlsx')}
ap=argparse.ArgumentParser();ap.add_argument('--expanded',action='store_true');ap.add_argument('--cross-code',action='store_true');ap.add_argument('--converted',action='store_true');args=ap.parse_args()
version,n=(6,19) if args.converted else (5,18) if args.cross_code else (4,16) if args.expanded else (2,12)
cells=[x for x in csv.DictReader((P['outputs_root']/f'diagnostics/efsa_scientific_exposure_admission/macp_37_execution_readiness_20260921_v{version}.csv').open()) if x['residue_definition_status'] in ['RD_EXACT','RD_CONVERSION_AVAILABLE']]
h={(r['country'],r['code']):r for r in csv.DictReader((d/f'current_{n}_cell_hbgv_20260921.csv').open())}
results=[];status=[]
for c in cells:
 name=c['active_substance'].split(' (')[0].lower();country=c['reporting_country'];adi=float(h[country,c['active_substance_code']]['adi'])
 run=f'{country}_2022_tomato_{name}'; files={b:d/f'{run}_{b}_20260921_detailed.xlsx' for b in ['LB','UB']}
 if not all(p.exists() for p in files.values()):status.append({'cell':run,'status':'NOT_COMPLETE'});continue
 for b,p in files.items():
  receipt=json.loads((d/f'{run}_{b}_20260921_receipt.json').read_text())
  inp=Path(receipt['input'])
  assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['output_sha256']
  assert hashlib.sha256(inp.read_bytes()).hexdigest()==receipt['input_sha256']
  iw=openpyxl.load_workbook(inp,read_only=True,data_only=True)
  assert iw['HBGV_Input'].cell(2,1).value==c['active_substance_code']
  active=[x for x in list(iw['OCCURRENCE_RPC'].values)[1:] if x[9] is not None]
  expected=float(c[f'risk_assessment_mean_{b.lower()}_mg_kg'] if args.converted else c[f'monitoring_mean_{b.lower()}_mg_kg'])
  assert len(active)==1 and active[0][4]=='A0DMX' and active[0][0]==c['active_substance_code']
  assert math.isclose(active[0][9],expected,rel_tol=1e-12,abs_tol=0)
  iw.close()
 data={b:{key(x):x for x in read(p)} for b,p in files.items()}
 assert set(data['LB'])==set(data['UB'])==set(baseline)
 for k in baseline:
  lo,hi=data['LB'][k],data['UB'][k]
  row={'occurrence_country':country,'survey_country':k[1],'survey':k[2],'population_group':k[0],'survey_n':lo['N subjects'],
       'year':int(c['year']),'commodity':c['commodity'],'rpc_code':c['rpc_code'],'pesticide':name,'pesticide_code':c['active_substance_code'],
       'programme':c['programme'],'sample_n':int(c['sample_n']),'quantified_n':int(c['quantified_n']),
       'adi_mg_kg_bw_day':adi,'RD_status':c['residue_definition_status'],'PF_status':'PF_NOT_REQUIRED_FOR_RAW_RPC_EQUIVALENT_ESTIMAND',
       'HRP_percentile':lo['HRP Comment'],'QC':'PASS_WITH_LIMITATION','consumption_provenance':'ORIGINAL_RPC_2018_STRONGLY_SUPPORTED',
       'scope':'SINGLE_RAW_TOMATO_TRANSPORTED_OCCURRENCE_SCENARIO_NOT_TOTAL_DIET'}
  for b in ['LB','UB']:
   x=data[b][k];conc=float(c[f'risk_assessment_mean_{b.lower()}_mg_kg'] if args.converted else c[f'monitoring_mean_{b.lower()}_mg_kg'])
   assert x['N subjects']==baseline[k]['N subjects'] and math.isclose(x['HBGV Value'],adi,rel_tol=1e-14,abs_tol=0)
   assert x['HBGV Type']=='ADI' and x['HBGV Unit'] in ['mg/kg bw/day','mg/kg bw per day']
   for metric in ['Mean Exposure (µg/kg bw per day)','HRP (µg/kg bw per day)','Exposure Chronic P95 (µg/kg bw per day)']:
    if x[metric] is None:assert baseline[k][metric] is None;continue
    assert math.isclose(x[metric],baseline[k][metric]*conc/.0045,rel_tol=1e-9,abs_tol=1e-11),(run,b,k,metric)
    assert hi[metric]>=lo[metric]>=0
   assert math.isclose(x['Mean exposure % ADI'],x['Mean Exposure (µg/kg bw per day)']/1000/adi*100,rel_tol=1e-10,abs_tol=1e-12)
   row[f'occurrence_{b}_mg_kg']=conc;row[f'exposure_mean_{b}_ug_kg_bw_day']=x['Mean Exposure (µg/kg bw per day)'];row[f'percent_ADI_mean_{b}']=x['Mean exposure % ADI']
   row[f'exposure_HRP_{b}_ug_kg_bw_day']=x['HRP (µg/kg bw per day)'];row[f'percent_ADI_HRP_{b}']=x['HRP (% ADI)']
   row[f'input_sha256_{b}']=json.loads((d/f'{run}_{b}_20260921_receipt.json').read_text())['input_sha256']
   row[f'output_sha256_{b}']=hashlib.sha256(files[b].read_bytes()).hexdigest()
  results.append(row)
 status.append({'cell':run,'status':'PASS_WITH_LIMITATION'})
completed=sum(x['status']=='PASS_WITH_LIMITATION' for x in status)
if completed:
 target=P['processed_data_root']/f'chronic_exposure_native_{completed}cells_20260921.parquet'
 if not target.exists():pq.write_table(pa.Table.from_pylist(results),target)
 else:assert pq.read_table(target).to_pylist()==results
report={'completed_cells':completed,'expected_cells':n,'paired_rows':len(results),'cells':status,'scientific_scope':'raw-RPC-equivalent transported single-food contribution; no totals or disease burden'}
t=d/f'qc_native_{completed}of{n}cells_20260921.json'
if not t.exists():
 with t.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
