"""Read existing official-source candidates; create new derived text, never edit raw."""
import csv,hashlib,json,subprocess
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];C=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(C['intermediate_data_root'])/'external_reference_v32_20261014';OUT.mkdir(exist_ok=True)
rows=list(csv.DictReader((ROOT/'00_admin/download_manifest.csv').open(encoding='utf-8-sig')))
sources=[]
for r in rows:
    if r.get('source_id') not in ['AU_FSANZ_ATDS','FSANZ_ATDS_19','FSANZ_ATDS_20']:continue
    p=Path(r['local_file_path'])
    if not any(x in str(p) for x in ['19th_ATDS','20th_ATDS','25th_ATDS']):continue
    h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==r['sha256'],p
    target=OUT/(p.stem+'.txt')
    if not target.exists():subprocess.run(['pdftotext','-layout',str(p),str(target)],check=True)
    sources.append(dict(path=str(p),sha256=h,text=str(target),source=r))
(OUT/'probe_manifest.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
print(json.dumps([dict(file=Path(x['path']).name,text=x['text'],sha256=x['sha256']) for x in sources],ensure_ascii=False,indent=2))
