"""Reuse existing admission evidence; never extrapolate code validation across countries."""
import argparse,csv,json
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
P={k.strip():Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
   if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
d=P['outputs_root']/'diagnostics/efsa_scientific_exposure_admission'
def read(name):return list(csv.DictReader((d/name).open()))
cells=read('cell_admission_status.csv');assert len(cells)==262
ap=argparse.ArgumentParser();ap.add_argument('--version',type=int,choices=[4,5,6],default=4);args=ap.parse_args();v=args.version
library={r['active_substance_code']:r for r in pq.read_table(P['processed_data_root']/f'pesticide_residue_definition_crosswalk_20260921_v{v}.parquet').to_pylist()}
ready=read(f'macp_37_execution_readiness_20260921_v{v}.csv')
admitted={(r['reporting_country'],r['rpc_code'],r['active_substance_code']) for r in ready if r['residue_definition_status'] in ['RD_EXACT','RD_CONVERSION_AVAILABLE']}
out=[]
for c in cells:
 key=tuple(c[k] for k in ['reporting_country','rpc_code','active_substance_code'])
 lib=library.get(c['active_substance_code']);tomato=c['rpc_code']=='P0231010A'
 if key in admitted:
  decision='PRIMARY_MACP_ADMISSIBLE';reason='2022 raw-tomato RD and programme-specific sample audit passed; native paired QC required separately'
 elif not c['macp_eligible_years'] and not c['mancp_eligible_years']:
  decision='EXCLUDE';reason='No programme/year stratum meets frozen n10 quantified3 complete-bounds rule'
 elif not tomato:
  decision='HOLD';reason='Tomato-specific RD and food-form library cannot be transferred to sweet pepper without commodity-specific validation'
 elif not lib:
  decision='HOLD';reason='No validated chemical-specific residue-definition library entry'
 elif lib['status']!='RD_EXACT':
  decision='HOLD';reason=lib['status']+': '+lib['limitations']
 else:
  decision='HOLD';reason='Definition is potentially reusable; source-country/year sample-level full-definition code/paramType and duplicate validation not completed for this stratum'
 out.append({**c,'current_classification':decision,'current_reason':reason,
  'library_status':lib['status'] if lib and tomato else 'NOT_APPLICABLE_OR_UNAUDITED',
  'semantics_current':'B_SUPPORTED_BY_METHOD_AND_IMPLEMENTATION',
  'consumption_current':'ORIGINAL_RPC_2018_STRONGLY_SUPPORTED',
  'PF_current':'PF_NOT_REQUIRED_FOR_RAW_RPC_EQUIVALENT_ESTIMAND' if tomato else 'PF_UNCERTAIN',
  'secondary_MANCP':'NOT_RELEASED_SEPARATE_SOURCE_AND_NATIVE_QC_REQUIRED',
  'interpretation':'Reporting market is distinct from survey country; no synthetic missing-country values'})
t=d/f'cell_admission_status_20260921_v{v}.csv'
if not t.exists():
 with t.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
else:assert list(csv.DictReader(t.open()))==out
summary={'records':len(out),'classification':dict(Counter(r['current_classification'] for r in out)),
 'scope':'Reassessment complete; unresolved underlying scientific requirements remain explicit, not declared completed',
 'secondary_exposure_released':False,'library':f'v{v}'}
rp=d/f'cell_admission_reassessment_20260921_v{v}.json'
if not rp.exists():
 with rp.open('x') as f:json.dump(summary,f,indent=2)
print(json.dumps(summary,indent=2))
