#!/usr/bin/env python3
"""Versioned single-pesticide scientific inputs from proven identity-repaired template."""
import argparse,csv,hashlib,json,math,re
from pathlib import Path
import openpyxl
ROOT=Path(__file__).resolve().parents[2]
P={k.strip():Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
   if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
d=P['outputs_root']/'diagnostics/primo_scientific_runs';out=d/'inputs';out.mkdir(exist_ok=True)
base=P['outputs_root']/'diagnostics/efsa_scientific_exposure_admission'
src=base/'macp_pilot/CZ_2022_tomato_azoxystrobin_LB_PRIMo4_pilot_v3_identity_repair_HOLD.xlsx'
assert hashlib.sha256(src.read_bytes()).hexdigest()=='7482dc6136e7a62ce3e1d557d495c4b407029fbc2d71faa5e3c2bd7362b7b886'
ap=argparse.ArgumentParser();ap.add_argument('--expanded',action='store_true');ap.add_argument('--cross-code',action='store_true');ap.add_argument('--converted',action='store_true');args=ap.parse_args()
version,n=(6,19) if args.converted else (5,18) if args.cross_code else (4,16) if args.expanded else (2,12)
cells=list(csv.DictReader((base/f'macp_37_execution_readiness_20260921_v{version}.csv').open()))
h={(r['country'],r['code']):r for r in csv.DictReader((d/f'current_{n}_cell_hbgv_20260921.csv').open())}
manifest=[]
for c in cells:
 if c['residue_definition_status'] not in ['RD_EXACT','RD_CONVERSION_AVAILABLE'] or c['active_substance']=='Azoxystrobin':continue
 if args.converted and c['active_substance']!='Phosphonic acid':continue
 if args.expanded and c['active_substance'] not in ['Indoxacarb','Propamocarb','Cyantraniliprole','Dimethomorph']:continue
 if args.cross_code and c['active_substance'] not in ['Abamectin','Hexythiazox']:continue
 hv=h[c['reporting_country'],c['active_substance_code']]
 name=c['active_substance'].split(' (')[0];code=c['active_substance_code']
 for b in ['LB','UB']:
  run=f'{c["reporting_country"]}_2022_tomato_{name.lower()}_{b}_20260921'
  target=out/(run+'.xlsx');value=float(c[f'risk_assessment_mean_{b.lower()}_mg_kg'] if args.converted else c[f'monitoring_mean_{b.lower()}_mg_kg'])
  if not target.exists():
   w=openpyxl.load_workbook(src);s=w['HBGV_Input']
   s.cell(2,1,code);s.cell(2,2,name);s.cell(2,5,float(hv['adi']));s.cell(2,7,f'EFSA2024 report published2026 AnnexIII Table3.2 row{hv["row"]}; {hv["authority"]}{hv["adi_year"]}')
   s.cell(2,8,'Chronic raw-RPC-equivalent only; current reference authority/date explicit')
   if s.max_row>2:s.delete_rows(3,s.max_row-2)
   for sheet in ['OCCURRENCE_RPC','OCCURRENCE_RPCD']:
    s=w[sheet]
    for rr in range(2,s.max_row+1):
     if s.cell(rr,3).value is not None:s.cell(rr,1,code);s.cell(rr,2,name)
   s=w['OCCURRENCE_RPC'];hits=[]
   for rr in range(2,s.max_row+1):
    if s.cell(rr,4).value=='P0231010-000' and s.cell(rr,5).value=='A0DMX':hits.append(rr)
    for col in [7,8,9,10,11,12,13,14,15,16]:s.cell(rr,col).value=None
   assert len(hits)==1;rr=hits[0]
   # Official parser retains leaf rows only if MRL is nonmissing. This routing value
   # is NOT a statutory MRL and never enters chronic calculation (explicit mean exists).
   s.cell(rr,7,value);s.cell(rr,9,'NONREGULATORY_ROUTING_VALUE_ONLY_NOT_A_LEGAL_MRL')
   s.cell(rr,10,value);s.cell(rr,16,f'MONITORING_MEAN_{b}; {c["reporting_country"]} 2022 K009A/ST10A raw tomato; NOT STMR; technical MRL field not regulatory; no MRL comparison')
   if args.converted:s.cell(rr,16,f'MONITORING_MEAN_{b}; complete fosetyl+phosphonic acid+salts sum converted from fosetyl to phosphonic acid equivalents using official0.75 ONCE before import; NOT parent-only assay; NOT STMR; MRL routing only')
   w.save(target);w.close()
  check=openpyxl.load_workbook(target,read_only=True,data_only=True)
  rpcs=list(check['OCCURRENCE_RPC'].values);active=[r for r in rpcs[1:] if r[6] is not None]
  assert len(active)==1 and active[0][0]==code and active[0][4]=='A0DMX' and abs(active[0][9]-value)<1e-12
  assert math.isclose(check['HBGV_Input'].cell(2,5).value,float(hv['adi']),rel_tol=1e-14,abs_tol=0);check.close()
  manifest.append(dict(run_id=run,input=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
      country=c['reporting_country'],pesticide=name,code=code,bound=b,occurrence=value,adi=float(hv['adi']),
      routing_mrl='NOT_REGULATORY_UNUSED_IN_CHRONIC',execution='NOT_YET_EXECUTED'))
mf=d/('converted_inputs_manifest_20260921.json' if args.converted else 'cross_code_exact_inputs_manifest_20260921.json' if args.cross_code else 'expanded_exact_inputs_manifest_20260921.json' if args.expanded else 'remaining_exact_inputs_manifest_20260921.json')
if not mf.exists():
 with mf.open('x') as f:json.dump(manifest,f,indent=2)
print(json.dumps({'inputs':len(manifest),'manifest':str(mf)}))
