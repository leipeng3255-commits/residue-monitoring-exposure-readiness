"""Assemble verified native results and bounded robustness tables without rerunning raw extraction."""
import csv,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
P={k.strip():Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
   if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
proc=P['processed_data_root'];out=P['outputs_root'];d=out/'diagnostics/efsa_scientific_exposure_admission'
tables=out/'tables/final_analysis_20260921';tables.mkdir(parents=True,exist_ok=True)
def read(p):return list(csv.DictReader(p.open()))
def write(name,rows):
 p=tables/name
 if p.exists():
  assert read(p)==[{k:'' if v is None else str(v) for k,v in r.items()} for r in rows];return
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
native=proc/'chronic_exposure_native_19cells_20260921.parquet'
qa=json.loads((out/'diagnostics/primo_scientific_runs/qc_native_19of19cells_20260921.json').read_text())
assert qa['completed_cells']==qa['expected_cells']==19
rows=pq.read_table(native).to_pylist();assert len(rows)==1672
metadata={(r['population_group'],r['country'],r['survey']):r for r in read(out/'diagnostics/efsa_rpc_primo_bridge/survey_metadata.csv')}
ready={(r['reporting_country'],r['active_substance_code']):r for r in read(d/'macp_37_execution_readiness_20260921_v6.csv')}
for r in rows:
 m=metadata[r['population_group'],r['survey_country'],r['survey']];c=ready[r['occurrence_country'],r['pesticide_code']]
 assert int(m['sample_size_chronic'])==r['survey_n']
 n=r['survey_n'];expected='P97_5' if n>118 else 'P95' if n>58 else 'P90' if n>28 else 'P75' if n>11 else None
 assert r['HRP_percentile']==expected
 r.update(age_group=r['population_group'],survey_start_year=int(m['survey_start_year']),survey_end_year=int(m['survey_end_year']),
          dietary_method=m['dietary_method'],survey_gap_to_monitoring_years=r['year']-int(m['survey_end_year']),
          high_percentile_reliability='NATIVE_N_DEPENDENT_HRP_NOT_UNIFORM_P95',
          uncertainty='CENSORING_ENDPOINTS_NOT_CONFIDENCE_INTERVALS; programme selection and processing/timing not bounded',
          monitoring_mean_source_LB_mg_kg=float(c['monitoring_mean_lb_mg_kg']),monitoring_mean_source_UB_mg_kg=float(c['monitoring_mean_ub_mg_kg']),
          RD_expression_factor=0.75 if r['RD_status']=='RD_CONVERSION_AVAILABLE' else 1.0,
          reference_authority='EFSA; current2024-report AnnexIII published2026',
          scope_level='EMPIRICAL_MARKET_OCCURRENCE_X_HISTORICAL_DIETARY_SCENARIO')
 for b in ['LB','UB']:
  assert math.isclose(r[f'occurrence_{b}_mg_kg'],r[f'monitoring_mean_source_{b}_mg_kg']*r['RD_expression_factor'],rel_tol=1e-12)
  assert r[f'percent_ADI_HRP_{b}']>=0
 assert r['percent_ADI_HRP_UB']>=r['percent_ADI_HRP_LB'] and r['percent_ADI_mean_UB']>=r['percent_ADI_mean_LB']
master=proc/'chronic_exposure_master.parquet'
if not master.exists():pq.write_table(pa.Table.from_pylist(rows),master)
else:assert pq.read_table(master).to_pylist()==rows
write('chronic_exposure_master.csv',rows)
groups=defaultdict(list)
for r in rows:groups[r['occurrence_country'],r['pesticide']].append(r)
summary=[]
for (country,pest),rr in sorted(groups.items()):
 x=rr[0];summary.append(dict(occurrence_country=country,pesticide=pest,year=2022,sample_n=x['sample_n'],quantified_n=x['quantified_n'],
  quantified_fraction=x['quantified_n']/x['sample_n'],occurrence_LB=x['occurrence_LB_mg_kg'],occurrence_UB=x['occurrence_UB_mg_kg'],
  UB_LB_ratio=x['occurrence_UB_mg_kg']/x['occurrence_LB_mg_kg'],ADI=x['adi_mg_kg_bw_day'],RD=x['RD_status'],
  survey_strata=len(rr),max_mean_percent_ADI_LB=max(r['percent_ADI_mean_LB'] for r in rr),
  max_mean_percent_ADI_UB=max(r['percent_ADI_mean_UB'] for r in rr),
  max_native_HRP_percent_ADI_UB=max(r['percent_ADI_HRP_UB'] for r in rr),
  any_UB_mean_above100=any(r['percent_ADI_mean_UB']>100 for r in rr)))
write('cell_results.csv',summary)
surveys={(r['population_group'],r['survey_country'],r['survey']):r for r in rows}
write('survey_metadata.csv',[{k:r[k] for k in ['population_group','survey_country','survey','survey_n','survey_start_year','survey_end_year','survey_gap_to_monitoring_years','dietary_method','HRP_percentile']} for r in surveys.values()])
sens=[]
for name,selected in [('exact_only',[r for r in rows if r['RD_status']=='RD_EXACT']),('exact_plus_expression_conversion',rows),
 ('sample_n_at_least50',[r for r in rows if r['sample_n']>=50]),('quantified_fraction_at_least10percent',[r for r in rows if r['quantified_n']/r['sample_n']>=.1]),
 ('survey_end_at_least2010',[r for r in rows if r['survey_end_year']>=2010])]:
 sens.append(dict(analysis=name,status='DESCRIPTIVE_SUBSET_NOT_NEW_PRIMARY',rows=len(selected),cells=len({(r['occurrence_country'],r['pesticide']) for r in selected}),
  max_mean_percent_ADI_UB=max(r['percent_ADI_mean_UB'] for r in selected),max_HRP_percent_ADI_UB=max(r['percent_ADI_HRP_UB'] for r in selected)))
write('robustness_subsets.csv',sens)
az=[{**{k:r[k] for k in ['occurrence_country','survey_country','survey','population_group']},
 'EFSA_ADI':.2,'JMPR2024_ADI':.03,'EFSA_mean_percent_ADI_UB':r['percent_ADI_mean_UB'],
 'JMPR_mean_percent_ADI_UB':r['exposure_mean_UB_ug_kg_bw_day']/1000/.03*100} for r in rows if r['pesticide']=='azoxystrobin']
write('azoxystrobin_reference_sensitivity.csv',az)
historical=json.loads((out/'diagnostics/us_benchmark_20260912T235750/independent_arithmetic_verification.json').read_text())
for path,expected in historical['file_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
us=read(out/'tables/us_benchmark_20260912T235750/current_exposure_summary.csv')
references={r['parameter_code']:r for r in read(ROOT/'01_protocol/toxicology_reference_candidates.csv')}
for r in us:
 ref=references[r['parameter']];assert math.isclose(float(r['ADI']),float(ref['ADI_upper_mg_kg_bw_day']),rel_tol=1e-12)
 r.update(pesticide=ref['active_ingredient'],reference_authority='JMPR; source-specific historical benchmark; not pooled with EFSA',
          percent_ADI_LB=float(r['HQ_lower'])*100,percent_ADI_UB=float(r['HQ_upper'])*100)
 for b in ['lower','upper']:assert math.isclose(float(r[f'EDI_{b}_mg_kg_bw_day']),float(r[f'concentration_{b}'])*float(r['intake_mean_g_kg_bw_day'])/1000,rel_tol=1e-12,abs_tol=1e-20)
write('US_historical_benchmark.csv',us)
report={'native_cells':19,'exact_cells':18,'conversion_cells':1,'paired_rows':len(rows),'survey_strata':len(surveys),
 'distinct_surveys':len({(r['survey_country'],r['survey']) for r in rows}),'diet_countries':len({r['survey_country'] for r in rows}),
 'occurrence_markets':sorted({r['occurrence_country'] for r in rows}),'pesticides':len({r['pesticide'] for r in rows}),
 'survey_end_range':[min(r['survey_end_year'] for r in rows),max(r['survey_end_year'] for r in rows)],
 'max_mean_percent_ADI_UB':max(r['percent_ADI_mean_UB'] for r in rows),'max_HRP_percent_ADI_UB':max(r['percent_ADI_HRP_UB'] for r in rows),
 'HRP_counts_unique_strata':dict(Counter(r['HRP_percentile'] for r in surveys.values())),
 'US_historical_rows':len(us),'US_prior_hashes':'ALL_PASS','no_disease_burden':True,
 'master_sha256':hashlib.sha256(master.read_bytes()).hexdigest()}
rp=tables/'analysis_qc.json'
if not rp.exists():
 with rp.open('x') as f:json.dump(report,f,indent=2)
else:assert json.loads(rp.read_text())==report
print(json.dumps(report,indent=2))
