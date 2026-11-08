"""Alternate pypdf reader and Decimal arithmetic; same scientist, no human validation."""
import csv,hashlib,json,re,sys
from pathlib import Path
from decimal import Decimal as D,localcontext
import yaml
sys.path.append('/path/to/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
out=Path(cfg['intermediate_data_root'])/'external_reference_v32_20261014'
m=json.loads((out/'probe_manifest.json').read_text())
src=next(x for x in m if Path(x['path']).name=='25th_ATDS_appendices.pdf')
assert hashlib.sha256(Path(src['path']).read_bytes()).hexdigest()==src['sha256']
reader=PdfReader(src['path']);primary=list(csv.DictReader((out/'fsanz_printed_rows.csv').open()))
expected={(int(x['page']),int(x['row_on_page'])):x for x in primary}
suffix=re.compile(r'(?:^|\s)(\d+)\s+(\d+)\s+(\d+)\s+(\d+(?:\.\d+)?)\s+(<LOR|\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$')
alternate=[]
for p in range(29,53):
    count=0
    for line in reader.pages[p-1].extract_text().splitlines():
        found=suffix.search(line)
        if not found:continue
        count+=1;v=found.groups();ref=expected[(p,count)]
        assert v==tuple(ref[k] for k in ['n','detects','pct','mean','minimum','maximum']),(p,count,v,ref)
        alternate.append(dict(page=p,row_on_page=count,n=v[0],detects=v[1],pct=v[2],mean=v[3],minimum=v[4],maximum=v[5],pypdf_line=line))
assert len(alternate)==348
with (out/'fsanz_alternate_numeric_rows.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(alternate[0]));w.writeheader();w.writerows(alternate)
checks=list(csv.DictReader((out/'fsanz_conditional_checks.csv').open()))
def bounds(s,m):
    x=D(s);unit=D(10)**x.as_tuple().exponent
    return max(D(0),x-unit*m),x+unit*m
for r in checks:
    with localcontext() as ctx:
        ctx.prec=50
        m=D('.5') if r['precision_assumption']=='half_display_unit' else D(1)
        lo,hi=bounds(r['printed_mean'],m);xl,xu=bounds(r['printed_maximum'],m)
        # Multiplication avoids recurring divisions at boundary contacts.
        ok=hi*D(r['n'])>=xl and lo*D(r['n'])<=xu*D(r['detects'])
        pok=abs(D(r['printed_percent'])*D(r['n'])-100*D(r['detects']))<=m*D(r['n'])
        assert str(ok)==r['conditional_mean_compatible'],r
        assert str(pok)==r['conditional_percent_compatible'],r
receipt=dict(numeric_rows_reextracted=348,numeric_fields_compared=348*6,arithmetic_row_assumptions_compared=len(checks),arithmetic_boolean_endpoints_compared=2*len(checks),all_agree=True,raw_sha256=src['sha256'],reader='pypdf independent of Poppler',arithmetic='Decimal multiplication independent of Fraction division',scope='Same investigator and shared assumptions; not independent human adjudication; not scientific accuracy certification',scripts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'05_code/quality_control/reconcile_fsanz_v32.py']})
(out/'fsanz_alternate_verification.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
