"""Stream the committed FDA table; preserve states and coordinates, no exposure."""
import csv
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
WORK=ROOT/'08_manuscript/source_transport_v28'
OUT=Path(cfg['intermediate_data_root'])/'fda_transport_challenge_v28'
commit=json.loads((WORK/'preanalysis_commitment.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(Path(r['path']))==r['sha256'] for r in commit['files'])
assert not OUT.exists(),'Preserve first-run outputs; use a versioned new directory.'
OUT.mkdir()
source=Path(cfg['raw_data_root'])/'fda_total_diet_study/2018_2022/TDS_Pesticides_Report_ByYear.xlsx'
ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
headers=['fiscal_year','calendar_year','collection','tds_food_no','tds_food_desc','tds_food_category','season','region','pesticide_code','analyte','concentration','units','lod','loq','pesticide_type','pesticide_class','cfr','mrl_ppb','violative','trace']
def num(x):
    try:
        d=Decimal(x)
        return d if d.is_finite() else None
    except (InvalidOperation,TypeError):return None
def stream(z,member,ss):
    with z.open(member) as f:
        parser=ET.iterparse(f,events=('start','end'));root=None
        for event,e in parser:
            if root is None:root=e
            if event!='end' or e.tag!=ns+'row':continue
            vals=['']*20
            for c in e:
                addr=re.match(r'[A-Z]+',c.attrib.get('r',''))[0];col=0
                for a in addr:col=col*26+ord(a)-64
                v=c.find(ns+'v');t=c.attrib.get('t')
                s=v.text if v is not None and v.text is not None else ''.join(c.itertext())
                if t=='s':s=ss[int(s)]
                vals[col-1]=s
            yield int(e.attrib['r']),vals
            e.clear();root.clear()
overall=Counter();state_stats=defaultdict(Counter);yearstats={};samples=set();foods=set();codes=set();keyhash=set();dup_count=0
examples={};anomalies=defaultdict(list);foodgroups=defaultdict(Counter);year_state=Counter()
start=time.time()
with zipfile.ZipFile(source) as z:
    ss=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    for ix,year in enumerate(range(2018,2023),1):
        stat=Counter();localkeys=set()
        for rn,vals in stream(z,f'xl/worksheets/sheet{ix}.xml',ss):
            if rn==1:assert vals==headers;continue
            if not any(vals):continue
            r=dict(zip(headers,vals));state=r['trace'] or 'EMPTY';loc=f'{year}!A{rn}:T{rn}'
            sample=tuple(r[k] for k in ['fiscal_year','calendar_year','collection','tds_food_no','season','region'])
            key=sample+(r['pesticide_code'],)
            kd=hashlib.sha256(json.dumps(key).encode()).digest()[:20]
            if kd in keyhash:
                dup_count+=1
                if len(anomalies['duplicate_candidate_key'])<12:anomalies['duplicate_candidate_key'].append({'source':loc,'row':r})
            keyhash.add(kd);samples.add(sample);localkeys.add(sample);foods.add((r['tds_food_no'],r['tds_food_desc']));codes.add((r['pesticide_code'],r['analyte']))
            v,l,q=[num(r[k]) for k in ['concentration','lod','loq']]
            props={'rows':True,'concentration_numeric':v is not None,'concentration_zero':v==0,'concentration_negative':v is not None and v<0,
                   'missing_lod':l is None,'missing_loq':q is None,'nonpositive_lod':l is not None and l<=0,'nonpositive_loq':q is not None and q<=0,
                   'lod_gt_loq':l is not None and q is not None and l>q,'value_below_lod':v is not None and l is not None and v<l,
                   'value_between_limits':v is not None and l is not None and q is not None and l<=v<q,
                   'value_ge_loq':v is not None and q is not None and v>=q,
                   'sheet_year_mismatch':r['fiscal_year']!=str(year)}
            for k,val in props.items():
                if val:stat[k]+=1;overall[k]+=1;state_stats[state][k]+=1
            stat['unit:'+r['units']]+=1;year_state[(year,state)]+=1
            foodgroups[(r['tds_food_no'],r['tds_food_desc'],r['tds_food_category'])][state]+=1
            if state not in examples and len(examples)<12:examples[state]={'source':loc,'row':r}
            for bad in ['concentration_negative','missing_lod','missing_loq','nonpositive_lod','nonpositive_loq','lod_gt_loq','sheet_year_mismatch']:
                if props[bad] and len(anomalies[bad])<12:anomalies[bad].append({'source':loc,'row':r})
            if rn%100000==0:print(f'{year}: {rn-1} rows',flush=True)
        stat['candidate_composite_keys']=len(localkeys);yearstats[str(year)]=dict(stat)
        print('YEAR COMPLETE',year,dict(stat),flush=True)
        (OUT/f'year_{year}_profile.json').write_text(json.dumps(dict(stat),indent=2))
assert sha(source)==commit['files'][-1]['sha256']
summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(source),'plan_sha256':commit['files'][0]['sha256'],
         'source_rows':overall['rows'],'source_programmes':1,'counts':dict(overall),'by_year':yearstats,'states':{k:dict(v) for k,v in state_stats.items()},
         'distinct_candidate_composite_keys':len(samples),'distinct_food_code_description_pairs':len(foods),'distinct_pesticide_code_name_pairs':len(codes),
         'duplicate_candidate_key_rows':dup_count,'distinct_candidate_result_keys':len(keyhash),'examples':examples,'anomalies':dict(anomalies),
         'sample_identity_limit':'Candidate collection/food keys are not certified individual retail sample IDs; no independent-person count inferred.',
         'validation_limit':'New full-row source reconciliation under a local plan; partly observed source, same development team; no human-performance evaluation.',
         'new_exposure_calculations':0,'runtime_seconds':round(time.time()-start,2)}
(OUT/'source_profile_first_run.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
with (OUT/'year_state_counts.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['sheet_year','source_trace_state','rows'])
    for (y,s),n in sorted(year_state.items()):w.writerow([y,s,n])
with (OUT/'food_state_counts.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['food_code','food_description','food_category','source_trace_state','rows'])
    for k,counts in sorted(foodgroups.items()):
        for state,n in sorted(counts.items()):w.writerow([*k,state,n])
print(json.dumps({k:summary[k] for k in ['source_rows','distinct_candidate_composite_keys','distinct_food_code_description_pairs','distinct_pesticide_code_name_pairs','duplicate_candidate_key_rows','states','runtime_seconds']},indent=2))
