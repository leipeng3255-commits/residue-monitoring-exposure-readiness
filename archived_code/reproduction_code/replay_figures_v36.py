"""Portable current eight-figure v36 replay from saved summaries, no new exposures."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--package',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();base=a.package.resolve();out=a.out.resolve()
out.mkdir(parents=True,exist_ok=False)
subprocess.run([sys.executable,str(base/'reproduction_code/replay_figures_v31.py'),
               '--package',str(base),'--out',str(out/'historical_v31')],check=True)
subprocess.run([sys.executable,str(base/'reproduction_code/source_stability_panels_v36.py'),
               '--data',str(base),'--out',str(out/'stability')],check=True)
fig=out/'figures';fig.mkdir()
for stem in ['figure_1_qualification','figure_2_primo','figure_3_disclosure',
             'figure_S1_organic_identification','figure_S2_information','figure_S3_comparison']:
    original=stem.replace('figure_S3_', 'figure_4_')
    for ext in ['svg','pdf','png','tiff']:
        shutil.copy2(out/'historical_v31/figures'/(original+'.'+ext),fig/(stem+'.'+ext))
for ext in ['svg','pdf','png','tiff']:
    shutil.copy2(out/'stability'/('figure_4_source_stability.'+ext),fig/('figure_4_source_stability.'+ext))
for ext in ['svg','pdf','png']:
    shutil.copy2(base/'grilling_v36/external_source_challenge'/('external_source_challenge.'+ext),
                 fig/('figure_S4_external_source_challenge.'+ext))
from PIL import Image
Image.open(fig/'figure_S4_external_source_challenge.png').convert('RGB').save(
    fig/'figure_S4_external_source_challenge.tiff',compression='tiff_lzw',dpi=(600,600))
for svg_path in sorted(fig.glob('*.svg')):
    svg_text=svg_path.read_text()
    assert '<text' in svg_text and '<image' not in svg_text, svg_path
receipt=dict(figure_count=8,panel_count=39,new_exposure_calculations=0,
             editable_vector_svg_count=8,
             saved_ADI_conversion_rechecks=json.loads((out/'historical_v31/replay_receipt.json').read_text())['saved_ADI_conversion_rechecks'],
             figures={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(fig.iterdir())},
             scope='Derived-summary plotting and saved-output checks. Figure 4D is a post hoc reporting-event diagnostic without inferential intervals; Figure S4 is an official-source field/arithmetic audit. Raw-source verification requires configured external originals.')
(out/'replay_receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:receipt[k] for k in ['figure_count','panel_count','new_exposure_calculations','saved_ADI_conversion_rechecks']}))
