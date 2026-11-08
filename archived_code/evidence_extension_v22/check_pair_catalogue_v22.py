"""Verify four source terms from the preserved official 2022 catalogue."""
import hashlib,io,json,zipfile
from pathlib import Path
import openpyxl
ROOT=Path(__file__).resolve().parents[2]
CFG={k.strip():json.loads(v.strip()) for l in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
     if l and not l.startswith('#') for k,v in [l.split(':',1)]}
p=Path(CFG['raw_data_root'])/'efsa_catalogues/zenodo_5949025/DCF_catalogues.zip'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
digest=sha(p);assert digest=='7ba62630db67f208fce417b0dc84a5d0d60ed43e18d3855b04e7f5efc4e000df'
expected={'A0C0S':'Unprocessed','A0DMX':'Tomatoes','A07SE':'Organic production','A0C6Y':'Conventional (non-organic) production'}
found={}
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    w=openpyxl.load_workbook(io.BytesIO(z.read('DCF_catalogues/MTX.xlsx')),read_only=True,data_only=True)
    for s in w:s.reset_dimensions()
    it=w['catalogue'].values;header=next(it);catalogue=dict(zip(header,next(it)))
    it=w['term'].values;header=next(it)
    for row in it:
        r=dict(zip(header,row))
        if r['termCode'] in expected:
            assert r['termExtendedName']==expected[r['termCode']]
            found[r['termCode']]={k:r[k] for k in ['termCode','termExtendedName','version','validFrom','status','deprecated']}
        if len(found)==4:break
    w.close()
assert len(found)==4 and catalogue['version']=='13.0' and sha(p)==digest
receipt={'source':'https://zenodo.org/records/5949025','source_sha256':digest,'member':'DCF_catalogues/MTX.xlsx',
 'catalogue_version':'13.0','catalogue_valid_from':catalogue['validFrom'],'terms':found,
 'scope_notes_paraphrased':['Unprocessed can include domain-specific treatment that leaves the relevant characteristics unchanged. It does not certify the food as eaten.',
 'The tomato term does not specify the part analysed; relevant law and additional facets determine it.',
 'Production terms classify the source declaration, not independent organic certification.'],
 'read_only_dimension_reset':True,'no_source_write':True,
 'access_note':'The combined direct web request for MCRA and EFSA9398 did not return and was terminated. The official MCRA indexed excerpt supported the initial interpretation; this later archived-catalogue check corroborates it.'}
out=ROOT/'00_admin/existing_data_evidence_v22_catalogue.json'
with out.open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print('Archived catalogue13.0: all4 terms matched; source hash/CRC unchanged.')
