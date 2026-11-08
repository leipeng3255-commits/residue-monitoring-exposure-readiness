#!/usr/bin/env python3
"""Read-only EFSA sample-metadata backfill and conservative chronic-admission audit.

The output is a new diagnostic, never a modification of source monitoring files.
Run the project check_paths.py before this script. No PRIMo calculations occur.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from zipfile import ZipFile

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
P = {k.strip(): Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
     if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
DATA, RAW, OUTROOT = P['data_root'], P['raw_data_root'], P['outputs_root']
OUT = OUTROOT/'diagnostics/efsa_scientific_exposure_admission'
BRIDGE = OUTROOT/'diagnostics/efsa_rpc_primo_bridge'
OLD = OUTROOT/'diagnostics/efsa_diet_linkage/final_admission_status.csv'
SCOPE = OUTROOT/'diagnostics/efsa_vegetable_scope_screen_20260920/primary_food_scope_screen.csv'
OBS = P['intermediate_data_root']/'efsa_2022_2024_sample_level_candidates_20260914T111235/candidate_sample_level_observations.csv.gz'
if not all(x.is_file() for x in (OLD,SCOPE,OBS,BRIDGE/'rpc_mapping.csv')) or not DATA.is_dir():
    raise RuntimeError('Required pinned external-drive inputs unavailable')
if OUT.exists():
    raise FileExistsError(f'No overwrite: {OUT}')

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def write(name, rows, fields):
    with (OUT/name).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

mapping={r['source_residue_rpc']:r for r in read(BRIDGE/'rpc_mapping.csv')}
country={'BE':'Belgium','CY':'Cyprus','CZ':'Czechia','DE':'Germany','DK':'Denmark','ES':'Spain',
         'FI':'Finland','FR':'France','GR':'Greece','HR':'Croatia','HU':'Hungary','IE':'Ireland',
         'IT':'Italy','NL':'Netherlands','PL':'Poland','RO':'Romania'}
annex=next((RAW/'efsa_zenodo/13220663').glob('Annex D - *.xlsx'))
wb=openpyxl.load_workbook(annex,read_only=True,data_only=True)
available={(str(r[1]),str(r[3])) for r in wb['Table D.1 RPC Cons Chronic'].iter_rows(min_row=2,values_only=True)
           if r[1] and r[3] and r[5]}
wb.close()
prior={ (r['sampling_country_code'],r['rpc_code'],r['active_substance_code']):r for r in read(OLD)}
scope={(r['sampling_country_code'],r['rpc_code'],r['active_substance_code']):r for r in read(SCOPE)
       if r['year']=='2022' and (r['food_scope_status']=='CANDIDATE_FOOD_SCOPE' or r['rpc_code']=='P0260040A')}
keys=sorted(k for k,r in prior.items() if r['final_status']=='HOLD' and k in scope and
            (country.get(k[0],k[0]),mapping[k[1]]['official_primo_rpc']) in available)
assert len(keys)==262, f'Candidate-set drift: expected 262, got {len(keys)}'
keyset=set(keys)

observations=defaultdict(list)
wanted=defaultdict(set)
with gzip.open(OBS,'rt',encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        key=(r['sampling_country_code'],r['rpc_code'],r['active_substance_code'])
        if key in keyset and r['year'] in ('2022','2023'):
            observations[(key,r['year'])].append(r)
            wanted[(r['year'],r['sampling_country_code'])].add(r['sample_id'])

# Metadata is deliberately recovered from preserved immutable source archives.
# This is needed because the locked sample-level candidate file omitted these fields.
meta=defaultdict(set)
targets=read(ROOT/'00_admin/efsa_2022_target_files.csv')
sources=[(r['country_code'],RAW/'efsa_zenodo'/r['record_id']/r['filename']) for r in targets]
sources.append(('*',RAW/'efsa_zenodo/17936507/Annex_VIII.zip'))
counts=Counter()
for code,path in sources:
    if not path.is_file(): raise FileNotFoundError(path)
    if code!='*' and not wanted.get(('2022',code)): continue
    with ZipFile(path) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        for name in names:
            proc=subprocess.Popen(['unzip','-p',str(path),name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            assert proc.stdout is not None
            with io.TextIOWrapper(proc.stdout,encoding='utf-8-sig',newline='') as f:
                for r in csv.DictReader(f):
                    year=r.get('sampY',''); reporting=r.get('sampCountry',''); sid=r.get('sampId_A','')
                    if sid not in wanted.get((year,reporting),()): continue
                    t=(year,reporting,sid)
                    meta[t].add((r.get('progType',''),r.get('sampStrategy',''),r.get('progLegalRef',''),
                                 r.get('origCountry',''),r.get('repCountry',''),r.get('sampMatCode.process','')))
                    counts['matched_source_result_rows']+=1
            error=proc.stderr.read().decode('utf-8','replace') if proc.stderr else ''
            if proc.wait(): raise RuntimeError(f'unzip failed: {path} {error[-300:]}')
    counts['archives_read']+=1

def classify(prog,strategy):
    if prog=='K009A' and strategy in ('ST10A','ST20A'):
        return 'EU_MACP_RANDOM' if strategy=='ST10A' else 'OTHER_UNKNOWN'
    if prog=='K005A': return 'MANCP_RISK_BASED'
    if prog in ('K019A','K038A'): return 'IMPORT_CONTROL'
    return 'OTHER_UNKNOWN'  # K018A national+EU: no sample/analyte attribution.

classified=[]; occ=defaultdict(lambda:{'rows':[],'countries':Counter(),'origins':Counter(),'codes':Counter()})
for (key,year),rows in sorted(observations.items()):
    for r in rows:
        idkey=(year,r['sampling_country_code'],r['sample_id'])
        variants=meta.get(idkey,set())
        # Source-row variation cannot be arbitrarily resolved at sample level.
        if len(variants)==1:
            prog,strategy,legal,origin,rep,process=next(iter(variants))
            label=classify(prog,strategy)
        else:
            prog=strategy=legal=origin=rep=process=''
            label='OTHER_UNKNOWN'
        rec=dict(year=year,reporting_country=r['sampling_country_code'],sample_id=r['sample_id'],
                 rpc_code=r['rpc_code'],active_substance_code=r['active_substance_code'],
                 programme_code=prog,sampling_strategy=strategy,legal_reference=legal,
                 programme_class=label,origin_country=origin,source_reporting_country=rep,
                 process_code=process,metadata_variants=len(variants),
                 classification_basis='SSD2 progType and sampStrategy; K018A unresolved mixed' if len(variants)==1 else 'NO_UNIQUE_SOURCE_METADATA')
        classified.append(rec)
        b=occ[(label,year,*key)];b['rows'].append(r);b['countries'][rep]+=1;b['origins'][origin]+=1;b['codes'][prog]+=1

OUT.mkdir(parents=True,exist_ok=False)
write('programme_classification.csv',classified,list(classified[0]))
occrows=[]
for (prog,year,c,rpc,active),b in sorted(occ.items()):
    rr=b['rows']; n=len(rr); q=sum(x['result_type']=='VAL' for x in rr)
    missing=sum(x['censor_limit_available']!='YES' or x['censor_upper_mg_kg']=='' for x in rr)
    conflict=sum(x['duplicate_conflict_flag']=='YES' for x in rr)
    lower=sum(float(x['censor_lower_mg_kg']) for x in rr)/n
    upper='' if missing else sum(float(x['censor_upper_mg_kg']) for x in rr)/n
    occrows.append(dict(programme=prog,year=year,reporting_country=c,rpc_code=rpc,
        active_substance_code=active,monitoring_mean_lb_mg_kg=lower,
        monitoring_mean_ub_mg_kg=upper,sample_n=n,quantified_n=q,non_detect_n=n-q,
        missing_loq_n=missing,loq_complete='YES' if not missing else 'NO',
        duplicate_conflict_n=conflict,programme_codes='|'.join(sorted(b['codes'])),
        source_reporting_countries=json.dumps(b['countries'],sort_keys=True),
        origin_distribution=json.dumps(b['origins'],sort_keys=True),
        meets_locked_n10_val3='YES' if n>=10 and q>=3 and not missing and not conflict else 'NO',
        estimand='EU_MARKET_MACP_STRATUM' if prog=='EU_MACP_RANDOM' else 'RISK_BASED_CONDITIONED' if prog=='MANCP_RISK_BASED' else 'UNRESOLVED',
        units='mg/kg',censoring='VAL:value; LOQ:[0,LOQ]; no midpoint'))
for label,name in [('EU_MACP_RANDOM','macp_occurrence_lbub.csv'),('MANCP_RISK_BASED','mancp_occurrence_lbub.csv')]:
    write(name,[r for r in occrows if r['programme']==label],list(occrows[0]))

# Exactly checked parent-only sentinel has a distinct, source-audited status;
# other substances are not promoted on active-substance name identity alone.
sentinel=read(BRIDGE/'residue_definition_audit.csv')
azoxy={r['monitoring_param_code'] for r in sentinel if r['classification']=='RESIDUE_DEFINITION_EXACT'}
resdef=[]; pf=[]; status=[]; timing=[]; origins=[]
surveys=read(BRIDGE/'survey_metadata.csv')
for key in keys:
    c,rpc,active=key; matching=[r for r in occrows if (r['reporting_country'],r['rpc_code'],r['active_substance_code'])==key]
    codes=sorted({d for year in ('2022','2023') for x in observations.get((key,year),[]) for d in x['residue_definition_codes'].split('|') if d})
    # Sentinel evidence may support EXACT only for the same code and audited substance;
    # source equality is not inferred for unverified chemical-specific definitions.
    rd='EXACT' if active in azoxy and len(codes)==1 else 'UNKNOWN'
    resdef.append(dict(reporting_country=c,rpc_code=rpc,active_substance_code=active,
                       enforcement_definition_codes='|'.join(codes),risk_assessment_definition='Azoxystrobin parent' if rd=='EXACT' else 'NOT_VERIFIED',
                       classification=rd,conversion_factor='',source='Sentinel residue_definition_audit.csv and cited EFSA opinion' if rd=='EXACT' else 'Per-chemical EU risk definition and conversion factor pending',
                       limitation='Sentinel source is not a blanket equivalence for other pesticides'))
    process={x['process_code'] for x in classified if (x['reporting_country'],x['rpc_code'],x['active_substance_code'])==key}
    pf.append(dict(reporting_country=c,rpc_code=rpc,active_substance_code=active,
                   source_process_codes='|'.join(sorted(process)),classification='PF_UNKNOWN',
                   factor='',factor_source='',consumption_conversion='PRIMo RPC/RYF is food quantity conversion',
                   residue_processing='Pesticide concentration change requires independent chemical/form PF',
                   raw_rpc_scenario='POSSIBLY_CONSERVATIVE_ONLY; not actual as-eaten exposure'))
    official=mapping[rpc]['official_primo_rpc']; survey_country=country.get(c,c)
    sv=[s for s in surveys if s['country']==survey_country and (survey_country,official) in available]
    for s in sv:
        end=s['survey_end_year']
        timing.append(dict(reporting_country=c,rpc_code=rpc,active_substance_code=active,
            survey_country=survey_country,population_group=s['population_group'],survey=s['survey'],
            survey_start=s['survey_start_year'],survey_end=end,residue_period='2022-2023',
            gap_from_2022_to_survey_end=str(2022-int(end)) if end.isdigit() else '',
            interpretation='TEMPORAL_LIMITATION_NOT_AUTOMATIC_EXCLUSION'))
    origins.append(dict(reporting_country=c,rpc_code=rpc,active_substance_code=active,
        primo_survey_country=survey_country,origin_by_programme_year=json.dumps({r['programme']+'_'+r['year']:r['origin_distribution'] for r in matching},sort_keys=True),
        interpretation='Reporting market, origin, and dietary-survey country are separate; no domestic-production inference'))
    macp=[r for r in matching if r['programme']=='EU_MACP_RANDOM' and r['meets_locked_n10_val3']=='YES']
    mancp=[r for r in matching if r['programme']=='MANCP_RISK_BASED' and r['meets_locked_n10_val3']=='YES']
    blockers=[]
    if not macp and not mancp:blockers.append('NO_PROGRAMME_STRATUM_WITH_LOCKED_N10_VAL3_COMPLETE_BOUNDS')
    if rd!='EXACT':blockers.append('RISK_RESIDUE_DEFINITION_UNVERIFIED')
    blockers.extend(('PESTICIDE_PROCESSING_FACTOR_UNRESOLVED','LIVE_PRIMO_CONSUMPTION_RDS_VERSION_UNCONFIRMED'))
    status.append(dict(reporting_country=c,rpc_code=rpc,vegetable=scope[key]['rpc_name'],
        active_substance_code=active,pesticide=scope[key]['active_substance_name'],
        primo_rpc=official,technical_bridge='YES',macp_eligible_years='|'.join(r['year'] for r in macp),
        mancp_eligible_years='|'.join(r['year'] for r in mancp),
        macp_sample_n=sum(int(r['sample_n']) for r in matching if r['programme']=='EU_MACP_RANDOM'),
        mancp_sample_n=sum(int(r['sample_n']) for r in matching if r['programme']=='MANCP_RISK_BASED'),
        residue_definition=rd,processing_factor='PF_UNKNOWN',consumption_version='PRIMo 4.0.1; LIVE RDS UNCONFIRMED',
        hierarchy='ONE_SELECTED_RPC_LEAF_ONLY',unit='mg/kg source; tool unit checked in sentinel',
        chronic_status='HOLD',acute_status='DEFERRED_SEPARATE_INPUT_GATE',reason='|'.join(blockers)))
write('residue_definition_audit.csv',resdef,list(resdef[0]))
write('processing_factor_audit.csv',pf,list(pf[0]))
write('survey_timing_audit.csv',timing,list(timing[0]) if timing else ['reporting_country'])
write('origin_interpretation.csv',origins,list(origins[0]))
write('cell_admission_status.csv',status,list(status[0]))
coverage=[]
for label in ('EU_MACP_RANDOM','MANCP_RISK_BASED','IMPORT_CONTROL','OTHER_UNKNOWN'):
    layer=[r for r in occrows if r['programme']==label]
    matching_keys={(r['reporting_country'],r['rpc_code'],r['active_substance_code']) for r in layer}
    surveyset={(t['survey_country'],t['population_group'],t['survey']) for t in timing if
               (t['reporting_country'],t['rpc_code'],t['active_substance_code']) in matching_keys}
    coverage.append(dict(programme=label,candidate_cells=len(matching_keys),cell_years=len(layer),
        eligible_cell_years=sum(r['meets_locked_n10_val3']=='YES' for r in layer),
        commodities=len({r['rpc_code'] for r in layer}),pesticides=len({r['active_substance_code'] for r in layer}),
        sample_analyte_observations=sum(r['sample_n'] for r in layer),
        unique_sample_ids=len({(r['year'],r['reporting_country'],r['sample_id']) for r in classified if r['programme_class']==label}),
        survey_populations=len(surveyset),population_coverage='NOT CALCULATED: Annex C subjects are not EU population weights'))
write('representative_coverage.csv',coverage,list(coverage[0]))

inputs=[OLD,SCOPE,OBS,BRIDGE/'rpc_mapping.csv',BRIDGE/'survey_metadata.csv',BRIDGE/'residue_definition_audit.csv']
receipt={'date':date.today().isoformat(),'candidate_cells':len(keys),'candidate_rows_recovered':len(classified),
         'metadata_rows_missing_or_conflicting':sum(x['metadata_variants']!=1 for x in classified),
         'source_archives_read':counts['archives_read'],'matched_source_result_rows':counts['matched_source_result_rows'],
         'status_counts':dict(Counter(r['chronic_status'] for r in status)),
         'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
         'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ('candidate_cells','candidate_rows_recovered','metadata_rows_missing_or_conflicting','source_archives_read','status_counts')},indent=2))
