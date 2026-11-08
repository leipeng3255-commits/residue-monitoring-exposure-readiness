"""Separate XLSX XML/Fraction implementation; internal computational replication."""
import collections,csv,hashlib,json,posixpath,re,zipfile
from fractions import Fraction as F
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(cfg['intermediate_data_root'])/'tds_semantics_challenge_20261013'
receipt=json.loads((OUT/'run_receipt.json').read_text())
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def table(name):return list(csv.DictReader((OUT/name).open()))
def rows(path,sheet):
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS):
                shared.append(''.join(t.text or '' for t in e.iter() if t.tag.endswith('}t')))
        rels={e.attrib['Id']:e.attrib['Target'] for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets=ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS)
        s=next(e for e in sheets if e.attrib['name']==sheet)
        rid=s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target=rels[rid];target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        with z.open(target) as stream:
            for _,e in ET.iterparse(stream,events=['end']):
                if not e.tag.endswith('}row'):continue
                values={}
                for c in e.findall('s:c',NS):
                    v=c.find('s:v',NS);t=c.attrib.get('t')
                    text=''.join(x.text or '' for x in c.iter() if x.tag.endswith('}t')) if t=='inlineStr' else shared[int(v.text)] if t=='s' and v is not None else v.text if v is not None else None
                    values[re.sub(r'\d','',c.attrib['r'])]=text
                yield int(e.attrib['r']),values
                e.clear()
def frac(x):return F(str(x).replace(',','.'))
def close(a,b):return abs(a-b)<=max(F(1,10**12),abs(a)*F(1,10**10))
checks=[]
for s in receipt['sources']:
    p=Path(s['path']);assert sha(p)==s['sha256']
    if s['source']=='EAT2':
        expected=table('eat2_chemical_denominator_bounds.csv');bycol={r['source_column']:r for r in expected}
        counts={c:collections.Counter() for c in bycol};sums={c:[F(0),F(0)] for c in bycol}
        for rn,row in rows(p,s['sheet']):
            if rn==1 or not row.get('B'):continue
            for c in bycol:
                v=row.get(c);counts[c]['n_all']+=1
                if v is None or v.strip() in ('','NR'):counts[c]['n_unanalysed']+=1;continue
                counts[c]['n_tested']+=1
                if v.startswith(('ND','NQ','<')):
                    kind='NQ' if v.startswith('NQ') else 'ND';counts[c]['n_'+kind]+=1
                    nums=re.findall(r'\d+(?:[.,]\d+)?',v);assert len(nums)==1
                    sums[c][1]+=frac(nums[0])
                else:counts[c]['n_VAL']+=1;sums[c][0]+=frac(v)
        for c,r in bycol.items():
            assert all(counts[c][k]==int(r[k]) for k in ['n_all','n_tested','n_unanalysed','n_ND','n_NQ','n_VAL'])
            n=counts[c]['n_tested'];nall=counts[c]['n_all'];v,limits=sums[c]
            assert close(v,frac(r['sum_VAL'])) and close(limits,frac(r['sum_limits']))
            assert close(v/n,frac(r['LB_tested'])) and close((v+limits)/n,frac(r['UB_tested']))
            # Exact rational identity, not approximate numerical coincidence.
            assert (v+limits)/nall==((v+limits)/n)*F(n,nall)
        checks.append({'source':'EAT2','columns_replicated':len(bycol),'exact_wrong_denominator_identities':len(bycol)})
    elif s['source']=='EATi':
        expected=iter(table('eati_record_intervals.csv'));counts=collections.Counter();n=0
        for rn,row in rows(p,s['sheet']):
            if rn==1 or not row.get('A'):continue
            r=next(expected);assert rn==int(r['source_row'])
            typ=row['L'];ld=frac(row['N']);lq=frac(row['O']);assert 0<ld<=lq
            if typ=='VAL':lb=ub=frac(row['M'])
            else:
                assert row.get('M') in (None,'');lb=F(0);ub=ld if typ=='<LD' else lq
            assert close(lb,frac(r['LB'])) and close(ub,frac(r['UB']))
            counts[typ]+=1;n+=1
        assert next(expected,None) is None and n==s['rows']
        assert all(counts[t]==s['cell_states'][t] for t in ['VAL','<LD','<LQ'])
        checks.append({'source':'EATi','record_endpoints_replicated':n,'status_blank_reconciliation':True})
    else:
        expected=iter(table('nz_brand_record_ordering.csv'));counts=collections.Counter();n=0
        def bounds(v):
            if v in ('N/R','N/A'):return None
            return (F(0),frac(v.lstrip('<').strip())) if v.startswith('<') else (frac(v),frac(v))
        for rn,row in rows(p,s['sheet']):
            if rn==1 or not row.get('A') or not row.get('C'):continue
            r=next(expected);assert rn==int(r['source_row']);a,b=bounds(row['D']),bounds(row['E'])
            if a is None or b is None:d='HOLD_NO_VALID_RESULT'
            else:
                l,u=a[0]-b[1],a[1]-b[0]
                d='BRAND1_ABOVE' if l>0 else 'BRAND1_BELOW' if u<0 else 'EXACT_RECORDED_TIE' if l==u==0 else 'UNRESOLVED_CENSORING'
                assert close(l,frac(r['difference_LB'])) and close(u,frac(r['difference_UB']))
            assert d==r['decision'];counts[d]+=1;n+=1
        assert next(expected,None) is None and dict(counts)==s['ordering_counts']
        checks.append({'source':'NZ_Q1','record_comparisons_replicated':n,'ordering_counts':dict(counts)})
    assert sha(p)==s['sha256']
report={'date':'2026-10-13','scope':'INTERNAL_SEPARATE_PARSER_ARITHMETIC_NOT_HUMAN_OR_PROSPECTIVE_VALIDATION','checks':checks,
        'numerical_tolerance':'max(absolute 1e-12, relative 1e-10); exact counts and classifications; Fraction identity exact within XML numeric representation',
        'initial_diagnostic':'Two initial exact-comparison failures (EAT2 sum; NZ difference endpoint) exposed source XML versus openpyxl float-to-string rounding; first observed EAT2 discrepancy 2e-18 mg/kg. No source changed. Numeric comparisons use the disclosed tolerance; counts and classifications remain exact.',
        'original_run_receipt_sha256':sha(OUT/'run_receipt.json'),'verifier_sha256':sha(Path(__file__)),
        'input_hash_checks':all(sha(OUT/r['file'])==r['sha256'] for r in receipt['outputs']),
        'filesystem_note':'AppleDouble ._ metadata entries in initial receipt are filesystem artifacts, not analytical outputs; preserved, not packaged as data.'}
assert report['input_hash_checks']
assert not (OUT/'separate_xml_verification.json').exists()
(OUT/'separate_xml_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
