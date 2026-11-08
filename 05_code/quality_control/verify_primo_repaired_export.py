#!/usr/bin/env python3
"""Preserve browser exports, compare with historical technical sentinel, never scientific admission."""
import hashlib
import json
import math
from pathlib import Path
import openpyxl

ROOT=Path(__file__).resolve().parents[2]
P={k.strip():Path(v.strip().strip('"')) for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
   if ':' in line and not line.lstrip().startswith('#') for k,v in [line.split(':',1)]}
out=P['outputs_root']/'diagnostics/primo_forensic'
history=P['outputs_root']/'diagnostics/efsa_rpc_primo_bridge/primo_outputs'
def rows(p):
    w=openpyxl.load_workbook(p,read_only=True,data_only=True)
    s=w.active;s.reset_dimensions();result=list(s.values);w.close();return result
receipts=[]
for kind,download in [('summary','chronic_summary-8.xlsx'),('detailed','chronic_detailed-7.xlsx')]:
    src=Path('/path/to/user/Downloads')/download
    dest=out/f'T02_LB_v5_{kind}_technical_recovery_20260921.xlsx'
    blob=src.read_bytes()
    if not dest.exists():
        with dest.open('xb') as f:f.write(blob)
    assert dest.read_bytes()==blob
    new=rows(dest);old=rows(history/f'T02_LB_chronic_{kind}_20260920.xlsx')
    assert new[0]==old[0] and len(new)==len(old)
    differences=[]; numeric_differences=[]
    for i,(a,b) in enumerate(zip(new[1:],old[1:]),2):
        for col,(x,y) in enumerate(zip(a,b)):
            if x==y:continue
            if isinstance(x,(float,int)) and isinstance(y,(float,int)):
                if not math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-14): numeric_differences.append([i,col,x,y])
            else:differences.append([i,col,x,y])
    assert not numeric_differences,numeric_differences
    # Only equivalent unit spelling may differ from UI-created historical HBGV.
    assert all(new[0][d[1]]=='HBGV Unit' and {d[2],d[3]} <= {'mg/kg bw/day','mg/kg bw per day'} for d in differences),differences
    receipts.append(dict(file=str(dest),sha256=hashlib.sha256(blob).hexdigest(),size_bytes=len(blob),
                         data_rows=len(new)-1,numeric_regression='PASS',unit_label_differences=len(differences)))
report=dict(status='TECHNICAL_END_TO_END_PASS_NOT_SCIENTIFIC_ADMISSION',exports=receipts,
            immutable_parent_sha256='214c8cdb451607baddea423e5275641cb9facffca945a20cb1269a18dc1e287d',
            repaired_input_sha256='b9d48df2118426a3a5381fadc4065381be0aff87f3676c8738a6b95c8ba1781b',
            note='Export contains automatic technical ADI ratios; not scientific pilot results. No new population burden calculation.')
with (out/'technical_recovery_verification_20260921.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
