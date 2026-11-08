"""Complete-sheet retrospective semantics audit; no exposure calculation."""
import collections, csv, hashlib, json, re, sys
from decimal import Decimal
from pathlib import Path
import yaml
sys.path.append('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
cfg = yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
RAW = Path(cfg['raw_data_root'])
OUT = Path(cfg['intermediate_data_root'])/'tds_semantics_challenge_20261013'
assert RAW.is_dir() and not OUT.exists(), 'Do not overwrite an earlier run'
OUT.mkdir()
D = Decimal

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def write_csv(name, data):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)

def number(x):
    v=D(str(x).strip().replace(',','.'))
    assert v.is_finite() and v>=0, x
    return v

manifest=list(csv.DictReader((ROOT/'00_admin/download_manifest.csv').open()))
spec=[('EAT2','france_anses_eat2/regional/PASER2006sa0361-An02.xlsx','Pesticides','A LIRE', ['B5','B7','B9','B11']),
      ('EATi','france_anses_eati/donnees_eati_20181128.xlsx','Résultats résidus de pesticides','MUST READ',['B11','B13','C30','C31','C32','C33','B37','B39']),
      ('NZ_Q1','new_zealand_mpi_total_diet_study/2024_Q1/NZTDS_2024_Q1_65331.xlsx','Table 1.1 All results','Contents',['A12','A39','A40','A41','A43','A44','A45'])]
receipt={'date':'2026-10-13','design':'RETROSPECTIVE_SOURCE_CHALLENGE_NOT_INDEPENDENT_HUMAN_VALIDATION',
         'protocol_sha256':sha(ROOT/'01_protocol/tds_semantics_challenge_20261013.md'),
         'code_sha256':sha(Path(__file__)), 'new_exposure_units':0,'sources':[], 'diagnostics':[]}
anchors=[]

for tag,rel,sheet,instructions,coords in spec:
    p=RAW/rel; digest=sha(p)
    matches=[r for r in manifest if r['local_file_path']==str(p) and r['sha256']==digest and int(r['bytes'])==p.stat().st_size]
    assert matches, p
    book=openpyxl.load_workbook(p,read_only=True,data_only=False)
    for coord in coords:
        anchors.append({'source':tag,'sheet':instructions,'cell':coord,'text':book[instructions][coord].value,
                        'raw_sha256':digest,'official_url':matches[-1]['official_url']})
    ws=book[sheet]; records=ws.iter_rows(values_only=True); headers=next(records)
    src={'source':tag,'path':str(p),'bytes':p.stat().st_size,'sha256':digest,'official_url':matches[-1]['official_url'],'sheet':sheet}
    if tag=='EAT2':
        assert len(headers)==329
        cols=[{'chemical':h,'source_column':openpyxl.utils.get_column_letter(i+8),'n_all':0,'n_tested':0,'n_unanalysed':0,'n_ND':0,'n_NQ':0,'n_VAL':0,'sum_VAL':D(0),'sum_limits':D(0)} for i,h in enumerate(headers[7:])]
        keys=set()
        for rn,row in enumerate(records,2):
            if not any(v is not None for v in row): continue
            assert row[6]=='mg/kg pf', (rn,row[6])
            key=tuple(row[:7]); assert key not in keys,(rn,key);keys.add(key)
            for s,v in zip(cols,row[7:]):
                s['n_all']+=1
                if v is None or str(v).strip() in ('','NR'):
                    s['n_unanalysed']+=1;continue
                t=str(v).strip()
                if t.startswith(('ND','NQ','<')):
                    m=re.fullmatch(r'(ND|NQ)\s*\(\s*([\d.,]+)\s*\)',t) or re.fullmatch(r'(<)\s*([\d.,]+)',t)
                    assert m,(rn,s['chemical'],v)
                    kind='NQ' if m[1]=='NQ' else 'ND'; limit=number(m[2]);assert limit>0
                    s['n_'+kind]+=1;s['sum_limits']+=limit
                else:
                    s['n_VAL']+=1;s['sum_VAL']+=number(v)
                s['n_tested']+=1
        for s in cols:
            n=s['n_tested'];nall=s['n_all']
            s['unit']='mg/kg fresh weight';s['LB_tested']=s['sum_VAL']/n if n else ''
            s['UB_tested']=(s['sum_VAL']+s['sum_limits'])/n if n else ''
            s['WRONG_LB_all_rows']=s['sum_VAL']/nall
            s['WRONG_UB_all_rows']=(s['sum_VAL']+s['sum_limits'])/nall
            s['denominator_attenuation_factor']=D(n)/nall if n else ''
            assert s['n_tested']+s['n_unanalysed']==s['n_all']
        write_csv('eat2_chemical_denominator_bounds.csv',cols)
        factors=sorted(s['denominator_attenuation_factor'] for s in cols if s['n_tested'])
        med=(factors[(len(factors)-1)//2]+factors[len(factors)//2])/2
        src.update({'rows':len(keys),'columns':len(cols),'cell_states':{k:sum(s[k] for s in cols) for k in ['n_all','n_tested','n_unanalysed','n_ND','n_NQ','n_VAL']},
                    'tested_columns':len(factors),'factor_min':str(min(factors)),'factor_median':str(med),'factor_max':str(max(factors)),
                    'mean_bound_interpretation':'Descriptive tested-composite expression means across sampled foods; no dietary weighting or pooling across chemicals'})
    elif tag=='EATi':
        h={v:i for i,v in enumerate(headers)};states=collections.Counter();keys=collections.Counter(); anomalies=[];details=[]
        for rn,row in enumerate(records,2):
            if not any(v is not None for v in row):continue
            typ=row[h['type_res']];v=row[h['concentration']];ld=number(row[h['ld']]);lq=number(row[h['lq']])
            assert 0<ld<=lq,(rn,ld,lq)
            assert row[h['unite']]=='µg/kg',(rn,row[h['unite']])
            blank=v is None or str(v).strip()==''
            assert typ in ('VAL','<LD','<LQ'),(rn,typ)
            if typ=='VAL':
                assert not blank;lb=ub=number(v)
                if ub<lq:anomalies.append({'row':rn,'substance':row[h['substance']],'value':str(ub),'ld':str(ld),'lq':str(lq),'issue':'VAL_BELOW_REPORTED_LQ_RETAINED_NOT_SILENTLY_RECLASSIFIED'})
            else:
                assert blank,(rn,typ,v);lb=D(0);ub=ld if typ=='<LD' else lq
            keys[(row[h['code']],row[h['substance']])]+=1
            states[typ]+=1;states['blank_concentration']+=int(blank)
            details.append({'source_row':rn,'code':row[h['code']],'food':row[h['food_item']],'substance':row[h['substance']],
                            'type_res':typ,'concentration_source':v,'ld':ld,'lq':lq,'LB':lb,'UB':ub,'unit':'µg/kg',
                            'WRONG_blank_zero_UB':0 if blank else ub})
        write_csv('eati_record_intervals.csv',details)
        if anomalies: write_csv('eati_quantification_limit_conflicts.csv',anomalies)
        src.update({'rows':len(details),'cell_states':dict(states),'duplicate_food_substance_keys':sum(v-1 for v in keys.values()),
                    'VAL_below_LQ_conflicts':len(anomalies),'blank_censored_records_with_positive_upper_bound':sum(r['type_res']!='VAL' and r['UB']>0 for r in details),
                    'interval_interpretation':'Record-level conservative censoring envelopes; no mean pooled across foods/chemicals, no risk-expression reconstruction'})
        # Disclosed examples are selected by source row within status, not by concentration extremes.
        examples=[next(r for r in details if r['type_res']==t) for t in ['<LD','<LQ','VAL']]
        write_csv('eati_source_linked_examples.csv',examples)
    else:
        def interval(v):
            t=str(v).strip()
            if t in ('N/R','N/A'):return None
            if t.startswith('<'):return D(0),number(t[1:])
            x=number(v);return x,x
        keys=set();pairs=[];counts=collections.Counter();states=collections.Counter()
        for rn,row in enumerate(records,2):
            if not row[0] or not row[2]:continue
            key=tuple(row[:3]);assert key not in keys,key;keys.add(key)
            assert row[5]=='mg/kg'
            intervals=[]
            for v in row[3:5]:
                assert v is not None
                t=str(v).strip();st='N/R' if t=='N/R' else 'N/A' if t=='N/A' else 'BELOW_LOQ' if t.startswith('<') else 'VAL';states[st]+=1
                intervals.append(interval(v))
            a,b=intervals
            if a is None or b is None:decision='HOLD_NO_VALID_RESULT';lb=ub=''
            else:
                lb=a[0]-b[1];ub=a[1]-b[0]
                assert lb<=ub
                decision='BRAND1_ABOVE' if lb>0 else 'BRAND1_BELOW' if ub<0 else 'EXACT_RECORDED_TIE' if lb==ub==0 else 'UNRESOLVED_CENSORING'
            counts[decision]+=1
            pairs.append({'source_row':rn,'commodity':row[0],'group':row[1],'compound':row[2],'brand1_source':row[3],'brand2_source':row[4],
                          'difference_LB':lb,'difference_UB':ub,'decision':decision,'unit':'mg/kg'})
        write_csv('nz_brand_record_ordering.csv',pairs)
        src.update({'rows':len(pairs),'cell_states':dict(states),'ordering_counts':dict(counts),
                    'inference':'Recorded four-unit brand-composite contrast, censoring only; not population or independent sampling inference'})
    book.close();assert sha(p)==digest;src['raw_sha_after_equal']=True;receipt['sources'].append(src)

write_csv('source_instruction_anchors.csv',anchors)
freeze=json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text())
assert len(freeze['files'])==95 and all(sha(Path(r['path']))==r['sha256'] for r in freeze['files'])
old=ROOT/'10_submission/最终投稿材料_v24_文件夹版';files=json.loads((old/'file_manifest.json').read_text())
assert all(sha(old/r['path'])==r['sha256'] for r in files)
receipt['preservation']={'frozen_pass':95,'v24_pass':len(files)}
receipt['outputs']=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.iterdir())]
(OUT/'run_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps(receipt,ensure_ascii=False,indent=2))
