"""Exact source-XML replication of group denominators; no numerical endpoint waiver."""
import ast,collections,csv,hashlib,json,posixpath,re,zipfile
from fractions import Fraction as F
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
ROOT=Path(__file__).resolve().parents[2];cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(cfg['intermediate_data_root'])/'tds_semantics_reassessment_v26_20261013'
receipt=json.loads((OUT/'reassessment_receipt.json').read_text())
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
reader=ROOT/'05_code/quality_control/verify_tds_semantics_xml_20261013.py';text=reader.read_text()
for n in ast.parse(text).body:
    if isinstance(n,ast.FunctionDef) and n.name=='rows':exec(compile(ast.get_source_segment(text,n),str(reader),'exec'),globals())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
oldcols=list(csv.DictReader((Path(cfg['intermediate_data_root'])/'tds_semantics_challenge_20261013/eat2_chemical_denominator_bounds.csv').open()))
checks=collections.defaultdict(collections.Counter);nrows=collections.Counter()
for rn,r in rows(Path(receipt['sources'][0]['path']),'Pesticides'):
    if rn==1 or not r.get('B'):continue
    g=r['A'];nrows[g]+=1
    for i,c in enumerate(oldcols,1):
        v=r.get(c['source_column']);t=v.strip() if v else ''
        st='UNANALYSED' if t in ('','NR') else 'NQ' if t.startswith('NQ') else 'ND' if t.startswith(('ND','<')) else 'VAL'
        checks[(g,i)][st]+=1
matrix=list(csv.DictReader((OUT/'eat2_group_chemical_coverage.csv').open()))
for r in matrix:
    d=checks[(r['source_group'],int(r['chemical_column']))];assert int(r['group_rows'])==nrows[r['source_group']]
    assert d['UNANALYSED']==int(r['n_unanalysed']) and d['ND']==int(r['n_ND']) and d['NQ']==int(r['n_NQ']) and d['VAL']==int(r['n_VAL'])
    assert d['ND']+d['NQ']+d['VAL']==int(r['n_tested'])
veg=[checks[('Légumes (hors pomme de terre)',i)] for i in range(1,323)]
factors=sorted(F(sum(v[k] for k in ['ND','NQ','VAL']),267) for v in veg if sum(v[k] for k in ['ND','NQ','VAL']))
assert len(factors)==275 and (factors[137])==F(255,267)
# Binary float is not involved in these exact denominator/status checks.
ct=collections.Counter()
for rn,r in rows(Path(receipt['sources'][1]['path']),'Résultats résidus de pesticides'):
    if rn==1 or not r.get('A'):continue
    st=r['L'];blank=r.get('M') in (None,'');ct[(st,blank)]+=1
    assert st in ('<LD','<LQ','VAL') and blank==(st!='VAL');assert 0<F(r['N'])<=F(r['O'])
assert sum(ct.values())==64112 and ct[('<LD',True)]==63350 and ct[('<LQ',True)]==583 and ct[('VAL',False)]==179
for s in receipt['sources']:assert sha(Path(s['path']))==s['sha256']
freeze=json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text());assert len(freeze['files'])==95 and all(sha(Path(s['path']))==s['sha256'] for s in freeze['files'])
old=ROOT/'10_submission/最终投稿材料_v25_文件夹版';m=json.loads((old/'file_manifest.json').read_text());assert len(m)==536 and all(sha(old/r['path'])==r['sha256'] for r in m)
out={'date':'2026-10-13','exact_group_chemical_cells_reconciled':len(matrix),'food_groups':36,'chemical_columns':322,'vegetable_tested_columns':275,'vegetable_untested_columns':47,
     'vegetable_median_exact':'255/267 = 85/89','vegetable_median_decimal':float(F(255,267)),'eati_status_records_reconciled':64112,
     'tolerance_for_counts_and_median':'NONE_EXACT_INTEGER_FRACTION_CHECK','raw_source_hashes_pass':3,'frozen_hashes_pass':95,'v25_preserved_hashes_pass':536,
     'scope':'Separate XML internal replication, not independent people or high-quality literature certification','receipt_sha256':sha(OUT/'reassessment_receipt.json'),'verifier_sha256':sha(Path(__file__))}
assert not (OUT/'exact_reassessment_verification.json').exists();(OUT/'exact_reassessment_verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
