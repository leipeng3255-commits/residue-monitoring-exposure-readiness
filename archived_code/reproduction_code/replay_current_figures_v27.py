"""Single entry point for all six current figures; saved aggregates only."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ap = argparse.ArgumentParser()
ap.add_argument('--package', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
base, out = a.package.resolve(), a.out.resolve()
cfg = yaml.safe_load((base / 'paths.yaml').read_text())
assert cfg['mode'] == 'saved_derived_replay_only'
assert not out.exists(), 'Use a new output directory; preserve previous replays.'
out.mkdir(parents=True)
jobs = [
    ('main_and_bounds', base / 'reproduction_code/portable_replay_v27.py', '--package', base),
    ('source_semantics', base / 'source_reassessment/tds_eight_panel_v26.py', '--data', base / 'source_reassessment'),
    ('production_comparison', base / 'reproduction_code/paired_concentration_v27.py', '--data', base / 'evidence_extension_v22')]
for name, script, flag, data in jobs:
    subprocess.run([sys.executable, str(script), flag, str(data), '--out', str(out / name)], check=True)
stems = {'figure_1_qualification': ('main_and_bounds', 3), 'figure_2_primo': ('main_and_bounds', 3),
         'figure_3_disclosure': ('source_semantics', 8), 'figure_S1_subsets': ('main_and_bounds', 2),
         'figure_S2_organic_identification': ('production_comparison', 3), 'figure_S3_information': ('main_and_bounds', 2)}
figures = out / 'figures'
figures.mkdir()
for stem, (stage, n) in stems.items():
    for ext in ['svg', 'pdf', 'png', 'tiff']:
        shutil.copy2(out / stage / (stem + '.' + ext), figures / (stem + '.' + ext))
    svg = (figures / (stem + '.svg')).read_text()
    assert '<text' in svg and '<image' not in svg
receipt = {'current_figure_count': len(stems), 'current_panel_count': sum(v[1] for v in stems.values()),
           'numeric_ADI_rechecks': json.loads((out / 'main_and_bounds/replay_validation.json').read_text())['percent_ADI_checks'],
           'figure_files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(figures.iterdir())},
           'generator_hashes': {str(s.relative_to(base)): hashlib.sha256(s.read_bytes()).hexdigest() for _,s,_,_ in jobs},
           'new_exposure_calculations': 0,
           'boundary': 'Saved-derived replay only; no raw-data access, internet, credentials, or hosted PRIMo execution. PDF/SVG metadata and fonts may change bytes between environments.'}
(out / 'current_replay_receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({k:receipt[k] for k in ['current_figure_count','current_panel_count','numeric_ADI_rechecks','new_exposure_calculations']}))
