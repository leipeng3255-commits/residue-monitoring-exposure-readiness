"""Source-specific re-adjudication and vegetable denominator audit; immutable originals."""
import collections,csv,hashlib,json,re,sys
from decimal import Decimal as D
from pathlib import Path
import yaml
sys.path.append('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
import openpyxl
ROOT=Path(__file__).resolve().parents[2];cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
RAW=Path(cfg['raw_data_root']);OLD=Path(cfg['intermediate_data_root'])/'tds_semantics_challenge_20261013';OUT=Path(cfg['intermediate_data_root'])/'tds_semantics_reassessment_v26_20261013'
assert RAW.is_dir() and not OUT.exists();OUT.mkdir()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(name,rows):
    with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def num(v):
    x=D(str(v).strip().replace(',','.'));assert x.is_finite() and x>=0;return x
old=json.loads((OLD/'run_receipt.json').read_text());assert all(sha(Path(s['path']))==s['sha256'] for s in old['sources'])
receipt={'date':'2026-10-13','scope':'RETROSPECTIVE_SOURCE_REASSESSMENT_NOT_NEW_EXPOSURE','protocol_sha256':sha(ROOT/'01_protocol/tds_reassessment_v26_20261013.md'),'code_sha256':sha(Path(__file__)),'sources':old['sources'],'new_exposure_units':0}
e2=Path(old['sources'][0]['path']);b=openpyxl.load_workbook(e2,read_only=True,data_only=False)
anchors=[]
for coord in ['B5','B7','B9','B11']:anchors.append({'source':'EAT2','sheet':'A LIRE','cell':coord,'text':b['A LIRE'][coord].value})
it=b['Pesticides'].iter_rows(values_only=True);head=next(it)
groups=collections.Counter();counts=collections.defaultdict(collections.Counter)
for row in it:
    if not row[1]:continue
    group=row[0];groups[group]+=1
    for i,v in enumerate(row[7:]):
        t=str(v).strip() if v is not None else '';st='UNANALYSED' if t in ('','NR') else 'NQ' if t.startswith('NQ') else 'ND' if t.startswith(('ND','<')) else 'VAL'
        if st=='VAL':num(v)
        counts[(group,i)][st]+=1
b.close();ordered=sorted(groups,key=lambda k:(-groups[k],k))
gc=[]
for rank,g in enumerate(ordered,1):
    for i,label in enumerate(head[7:]):
        n=counts[(g,i)];nt=n['ND']+n['NQ']+n['VAL'];assert sum(n.values())==groups[g]
        gc.append({'group_rank':rank,'source_group':g,'group_rows':groups[g],'chemical_column':i+1,'chemical':label,'n_tested':nt,'n_unanalysed':n['UNANALYSED'],'n_ND':n['ND'],'n_NQ':n['NQ'],'n_VAL':n['VAL'],'tested_fraction':str(D(nt)/groups[g]),'mean_status':'DEFINED_TESTED_RECORD_DOMAIN' if nt else 'HOLD_NO_TESTED_RECORD'})
write('eat2_group_chemical_coverage.csv',gc)
vegetable='Légumes (hors pomme de terre)';assert groups[vegetable]==267
oldcols=list(csv.DictReader((OLD/'eat2_chemical_denominator_bounds.csv').open()));cols=[]
for i,r in enumerate(oldcols):
    ns=counts[(vegetable,i)];nt=ns['ND']+ns['NQ']+ns['VAL']
    tally=collections.Counter()
    for g in groups:tally.update(counts[(g,i)])
    assert tally['UNANALYSED']==int(r['n_unanalysed']) and tally['VAL']==int(r['n_VAL']) and sum(tally.values())==1193
    cols.append({'chemical':r['chemical'],'chemical_column':i+1,'whole_n_all':1193,'whole_n_tested':int(r['n_tested']),'whole_factor':r['denominator_attenuation_factor'],
                 'vegetable_n_all':267,'vegetable_n_tested':nt,'vegetable_n_VAL':ns['VAL'],'vegetable_n_ND':ns['ND'],'vegetable_n_NQ':ns['NQ'],
                 'vegetable_factor':str(D(nt)/267) if nt else '', 'vegetable_mean_status':'DEFINED_TESTED_RECORD_DOMAIN' if nt else 'HOLD_NO_TESTED_RECORD'})
write('eat2_whole_and_vegetable_denominators.csv',cols)
vf=sorted(D(r['vegetable_factor']) for r in cols if r['vegetable_factor']);med=(vf[(len(vf)-1)//2]+vf[len(vf)//2])/2
receipt['eat2_reassessment']={'source_groups':len(groups),'source_rows':sum(groups.values()),'vegetable_rows':267,'whole_columns':322,'vegetable_columns_with_analysis':len(vf),'vegetable_columns_without_analysis':322-len(vf),
    'whole_median_factor':old['sources'][0]['factor_median'],'vegetable_median_factor':str(med),'vegetable_min_factor':str(min(vf)),'vegetable_max_factor':str(max(vf)),
    'vegetable_analysed_cells':sum(r['vegetable_n_tested'] for r in cols),'vegetable_quantified_cells':sum(r['vegetable_n_VAL'] for r in cols),'vegetable_unanalysed_cells':267*322-sum(r['vegetable_n_tested'] for r in cols)}
e1=Path(old['sources'][1]['path']);b=openpyxl.load_workbook(e1,read_only=True,data_only=False)
for c in ['B11','B13','B37','B39']:anchors.append({'source':'EATi','sheet':'MUST READ','cell':c,'text':b['MUST READ'][c].value})
it=b['Résultats résidus de pesticides'].iter_rows(values_only=True);h={x:i for i,x in enumerate(next(it))}
ct=collections.Counter();dist=collections.Counter();chem=collections.defaultdict(collections.Counter);examples=[];exam_counts=collections.Counter()
for rn,r in enumerate(it,2):
    if not r[0]:continue
    st=r[h['type_res']];blank=r[h['concentration']] is None or str(r[h['concentration']]).strip()=='';ld,lq=num(r[h['ld']]),num(r[h['lq']]);assert 0<ld<=lq
    assert st in ('<LD','<LQ','VAL') and blank==(st!='VAL')
    ct[(st,blank)]+=1;chem[r[h['substance']]][st]+=1
    if st=='VAL':v=num(r[h['concentration']]);assert v>=lq;lower=upper=v
    else:
        lower=D(0);upper=ld if st=='<LD' else lq;dist[(st,str(upper))]+=1
    if exam_counts[st]<2:
        examples.append({'source_row':rn,'food_code':r[h['code']],'food':r[h['food_item']],'chemical':r[h['substance']],'type_res':st,'ld':str(ld),'lq':str(lq),'primary_lower':str(lower),'primary_upper':str(upper),
                         'reporting_state_conditional_lower':str(ld if st=='<LQ' else lower),'upper_over_lq':str(upper/lq),'lower_over_lq':str(lower/lq),'conditional_lower_over_lq':str((ld if st=='<LQ' else lower)/lq),'unit':'µg/kg'})
        exam_counts[st]+=1
b.close();write('eati_blank_type_reconciliation.csv',[{'type_res':st,'concentration_blank':bl,'records':n} for (st,bl),n in ct.items()])
write('eati_censor_threshold_distribution.csv',[{'type_res':st,'upper_limit_ug_kg':v,'records':n} for (st,v),n in sorted(dist.items())])
write('eati_source_interval_examples.csv',examples)
write('eati_chemical_support.csv',[{'chemical':k,'tested_records':sum(v.values()),'n_VAL':v['VAL'],'n_below_LD':v['<LD'],'n_below_LQ':v['<LQ']} for k,v in sorted(chem.items())])
write('source_instruction_anchors.csv',anchors)
receipt['eati_reassessment']={'records':sum(ct.values()),'blank_censored_records':sum(n for (s,b),n in ct.items() if b),'quantified_records':sum(n for (s,b),n in ct.items() if s=='VAL'),
    'chemical_expressions':len(chem),'sample_examples':len(examples),'zero_lower_substitution_valid_if_declared':True,'zero_as_observed_or_upper_value':'INVALID','risk_sum_or_exposure_admission':'NOT_PERFORMED'}
assert receipt['eati_reassessment']['blank_censored_records']==63933
for s in old['sources']:assert sha(Path(s['path']))==s['sha256']
for file in ['nz_brand_record_ordering.csv']:shutil=None # raw rows stay external; no extra copy required
receipt['outputs']=[{'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file() and not p.name.startswith('._')]
(OUT/'reassessment_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps({k:receipt[k] for k in ['eat2_reassessment','eati_reassessment']},ensure_ascii=False,indent=2))
