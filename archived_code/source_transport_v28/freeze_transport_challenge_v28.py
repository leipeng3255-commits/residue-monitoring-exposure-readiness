"""Local pre-analysis commitment; records existing source knowledge and immutable hashes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=ROOT/'08_manuscript/source_transport_v28'
OUT.mkdir(exist_ok=True)
target=OUT/'preanalysis_commitment.json'
assert not target.exists(),'Preserve the existing commitment; use a separately dated amendment.'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
raw=Path(cfg['raw_data_root'])/'fda_total_diet_study/2018_2022/TDS_Pesticides_Report_ByYear.xlsx'
assert sha(raw)=='69aa946a5e24ec85986a827e11217dc62bfd9eaa62e3d70daa916fb94f0f0c18'
base=ROOT/'10_submission/最终投稿材料_v27_科学终审_文件夹版'
manifest=json.loads((base/'file_manifest.json').read_text())
assert len(manifest)==381 and all(sha(base/r['path'])==r['sha256'] for r in manifest)
frozen=json.loads((ROOT/'00_admin/analysis_freeze_manifest_20260921.json').read_text())['files']
assert len(frozen)==95 and all(sha(Path(r['path']))==r['sha256'] for r in frozen)
paths=[ROOT/'01_protocol/fda_transport_challenge_v28_20261013.md',
       base/'01_Food_Control/manuscript.md',
       base/'03_可复现数据与代码_NOT_DIRECT_UPLOAD/question_rules_v23/question_interval_rules_v23_20261009.md',raw]
record={'committed_at_utc':datetime.now(timezone.utc).isoformat(),'public_preregistration':False,
        'prior_knowledge':'Programme docs plus prior source hash, header/first-year-row and sheet row-count audits; no current full result-state analysis before this commitment.',
        'human_independence':False,'v27_files_preserved':381,'parent_frozen_preserved':95,
        'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]}
target.write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps(record,ensure_ascii=False,indent=2))
