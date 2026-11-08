"""Second reader: library decoding, independent counters, retained threshold discrepancies."""
import hashlib,json,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import yaml
sys.path.append('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
import openpyxl

ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(cfg['intermediate_data_root'])/'fda_transport_challenge_v28'
SOURCE=Path(cfg['raw_data_root'])/'fda_total_diet_study/2018_2022/TDS_Pesticides_Report_ByYear.xlsx'
TARGET=OUT/'openpyxl_verification_first_run.json'
assert not TARGET.exists()
rawhash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
primary=json.loads((OUT/'source_profile_first_run.json').read_text())
assert rawhash==primary['source_sha256']
book=openpyxl.load_workbook(SOURCE,read_only=True,data_only=True)
totals=Counter();years={};examples={};near=[];state_counts=Counter();foodstates=Counter();t=time.time()
for name in book.sheetnames:
    sheet=book[name];it=sheet.iter_rows(values_only=True);header=next(it);idx={x:i for i,x in enumerate(header)}
    count=Counter();keys=set();last=1
    for n,row in enumerate(it,2):
        if not any(x is not None for x in row):continue
        last=n;get=lambda x:row[idx[x]]
        v,l,q=[get(x) for x in ['concentration','lod','loq']]
        state=get('trace');state_counts[state]+=1
        count['rows']+=1
        count['concentration_numeric']+=isinstance(v,(int,float))
        count['concentration_zero']+=(v==0)
        count['value_below_lod']+=(v<l)
        count['value_between_limits']+=(l<=v<q)
        count['value_ge_loq']+=(v>=q)
        count['unit:'+get('units')]+=1
        key=tuple(get(k) for k in ['fiscal_year','calendar_year','collection','tds_food_no','season','region']);keys.add(key)
        foodstates[(str(get('tds_food_no')),get('tds_food_desc'),get('tds_food_category'),state)]+=1
        if state not in examples:examples[state]={'source':f'{name}!A{n}:T{n}','row':dict(zip(header,row))}
        if v!=0 and (abs(v-l)<=1e-12*max(1,abs(v),abs(l)) or abs(v-q)<=1e-12*max(1,abs(v),abs(q))):
            count['near_numeric_boundary']+=1
            if len(near)<20:near.append({'source':f'{name}!A{n}:T{n}','concentration':v,'lod':l,'loq':q})
        if n%150000==0:print(name,n-1,flush=True)
    count['candidate_composite_keys']=len(keys);years[name]=dict(count)
    for k,v in count.items():totals[k]+=v
    print('SECOND READER YEAR',name,count['rows'],flush=True)
book.close()
discrepancies=[]
for year,stat in primary['by_year'].items():
    for key,v in stat.items():
        if years[year].get(key,0)!=v:discrepancies.append({'year':year,'metric':key,'xml_decimal':v,'openpyxl_float':years[year].get(key,0)})
import csv
reference_food={(r['food_code'],r['food_description'],r['food_category'],r['source_trace_state']):int(r['rows']) for r in csv.DictReader((OUT/'food_state_counts.csv').open())}
food_mismatch=[{'key':k,'primary':v,'second':foodstates.get(k)} for k,v in reference_food.items() if foodstates.get(k)!=v]
assert len(reference_food)==len(foodstates)
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==rawhash
record={'completed_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':rawhash,'reader':'openpyxl '+openpyxl.__version__,
        'primary_reader':'stdlib XML streaming with Decimal lexical comparisons','by_year':years,'totals':dict(totals),'state_counts':dict(state_counts),
        'first_state_examples':examples,'food_state_comparisons':len(reference_food),'food_state_discrepancies':food_mismatch,
        'threshold_and_count_discrepancies':discrepancies,'near_numeric_boundary_examples':near,
        'status':'PASS' if not discrepancies and not food_mismatch else 'DISCREPANCIES_RETAINED',
        'not_independent_assessors':True,'seconds':round(time.time()-t,2)}
TARGET.write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps({k:record[k] for k in ['status','totals','food_state_comparisons','threshold_and_count_discrepancies','seconds']},indent=2))
