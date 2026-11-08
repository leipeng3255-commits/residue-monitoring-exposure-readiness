"""Portable six-figure replay; v30 supplies four unchanged figures only."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
base=a.package.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
subprocess.run([sys.executable,str(base/'reproduction_code/replay_figures_v30.py'),'--package',str(base),'--out',str(out/'historical')],check=True)
subprocess.run([sys.executable,str(base/'reproduction_code/depth_panels_v31.py'),'--data',str(base),'--out',str(out/'depth')],check=True)
fig=out/'figures';fig.mkdir()
for stem in ['figure_1_qualification','figure_2_primo','figure_3_disclosure','figure_4_comparison','figure_S1_organic_identification','figure_S2_information']:
    origin=out/'depth' if stem.startswith(('figure_1_','figure_2_')) else out/'historical/figures'
    for ext in ['svg','pdf','png','tiff']:shutil.copy2(origin/(stem+'.'+ext),fig/(stem+'.'+ext))
receipt=dict(figure_count=6,panel_count=31,new_exposure_calculations=0,
    saved_ADI_conversion_rechecks=json.loads((out/'historical/replay_receipt.json').read_text())['saved_ADI_conversion_rechecks'],
    figures={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(fig.iterdir())},
    scope='Derived-figure replay only. Raw-source reconstruction and deletion verification require project paths and external source extracts.')
(out/'replay_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:receipt[k] for k in ['figure_count','panel_count','new_exposure_calculations','saved_ADI_conversion_rechecks']}))
