"""Regenerate six current figures, with isolated legacy replay for two unchanged supplements."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import yaml
p=argparse.ArgumentParser();p.add_argument('--package',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
base=a.package.resolve();out=a.out.resolve()
cfg=yaml.safe_load((base/'paths.yaml').read_text());assert cfg['mode']=='saved_derived_replay_only'
assert not out.exists();out.mkdir(parents=True)
jobs=[('quantitative',base/'reproduction_code/quantitative_panels_v30.py',['--data',str(base)]),
      ('source',base/'reproduction_code/source_semantics_ten_v30.py',['--data',str(base),'--config',str(base/'paths.yaml')]),
      ('legacy_bounds',base/'reproduction_code/portable_replay_v27.py',['--package',str(base)]),
      ('organic',base/'reproduction_code/paired_concentration_v27.py',['--data',str(base/'evidence_extension_v22')])]
for name,code,flags in jobs:subprocess.run([sys.executable,str(code),*flags,'--out',str(out/name)],check=True)
fig=out/'figures';fig.mkdir()
mapping={'figure_1_qualification':('quantitative','figure_1_qualification',6),
         'figure_2_primo':('quantitative','figure_2_primo',6),
         'figure_3_disclosure':('source','figure_3_disclosure',10),
         'figure_4_comparison':('quantitative','figure_4_comparison',4),
         'figure_S1_organic_identification':('organic','figure_S2_organic_identification',3),
         'figure_S2_information':('legacy_bounds','figure_S3_information',2)}
for name,(stage,old,n) in mapping.items():
    for ext in ['svg','pdf','png','tiff']:shutil.copy2(out/stage/(old+'.'+ext),fig/(name+'.'+ext))
receipt={'figure_count':6,'panel_count':31,'new_exposure_calculations':0,
 'saved_ADI_conversion_rechecks':json.loads((out/'legacy_bounds/replay_validation.json').read_text())['percent_ADI_checks'],
 'figures':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(fig.iterdir())},
 'scope':'Saved aggregates only; the isolated legacy stage regenerates historical diagnostics to obtain the unchanged below-LOQ supplement. Only the six filesets in figures/ are current. Metadata/font versions may change file bytes.'}
(out/'replay_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:receipt[k] for k in ['figure_count','panel_count','saved_ADI_conversion_rechecks','new_exposure_calculations']}))
