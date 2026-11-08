"""Fresh read-only replay of saved quantitative claims, with a new receipt."""
import ast
import collections
import csv
import hashlib
import json
import posixpath
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
cfg = yaml.safe_load((ROOT / '00_admin/paths.yaml').read_text())
subprocess.run(['python3', str(ROOT / '05_code/utilities/check_paths.py')], check=True)
BASE = ROOT / '10_submission/最终投稿材料_v26_文件夹版'
OUT = ROOT / '08_manuscript/adversarial_revision_v27/core_recheck.json'
assert not OUT.exists()

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

records = json.loads((BASE / 'file_manifest.json').read_text())
assert len(records) == 561
assert all(sha(BASE / r['path']) == r['sha256'] for r in records)
freeze = json.loads((ROOT / '00_admin/analysis_freeze_manifest_20260921.json').read_text())['files']
assert len(freeze) == 95 and all(sha(Path(r['path'])) == r['sha256'] for r in freeze)
source = Path(cfg['intermediate_data_root']) / 'tds_semantics_reassessment_v26_20261013'
receipt = json.loads((source / 'reassessment_receipt.json').read_text())
assert all(sha(Path(r['path'])) == r['sha256'] for r in receipt['sources'])
reader = ROOT / '05_code/quality_control/verify_tds_semantics_xml_20261013.py'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
code = reader.read_text()
for node in ast.parse(code).body:
    if isinstance(node, ast.FunctionDef) and node.name == 'rows':
        exec(compile(ast.get_source_segment(code, node), str(reader), 'exec'), globals())
columns = list(csv.DictReader((Path(cfg['intermediate_data_root']) / 'tds_semantics_challenge_20261013/eat2_chemical_denominator_bounds.csv').open()))
counts = collections.defaultdict(collections.Counter)
group_n = collections.Counter()
for rn, r in rows(Path(receipt['sources'][0]['path']), 'Pesticides'):
    if rn == 1 or not r.get('B'):
        continue
    group_n[r['A']] += 1
    for i, col in enumerate(columns, 1):
        v = (r.get(col['source_column']) or '').strip()
        status = 'UNANALYSED' if v in ('', 'NR') else 'NQ' if v.startswith('NQ') else 'ND' if v.startswith(('ND', '<')) else 'VAL'
        counts[(r['A'], i)][status] += 1
matrix = list(csv.DictReader((source / 'eat2_group_chemical_coverage.csv').open()))
for r in matrix:
    c = counts[(r['source_group'], int(r['chemical_column']))]
    assert int(r['group_rows']) == group_n[r['source_group']]
    for k, field in [('UNANALYSED', 'n_unanalysed'), ('ND', 'n_ND'), ('NQ', 'n_NQ'), ('VAL', 'n_VAL')]:
        assert c[k] == int(r[field])
all_status = sum(counts.values(), collections.Counter())
assert all_status == {'UNANALYSED': 223520, 'ND': 159561, 'NQ': 374, 'VAL': 691}
v = [counts[('Légumes (hors pomme de terre)', i)] for i in range(1, 323)]
factors = sorted(F(sum(c[k] for k in ['ND', 'NQ', 'VAL']), 267) for c in v if sum(c[k] for k in ['ND', 'NQ', 'VAL']))
assert len(factors) == 275 and factors[137] == F(255, 267)
eati = collections.Counter()
for rn, r in rows(Path(receipt['sources'][1]['path']), 'Résultats résidus de pesticides'):
    if rn == 1 or not r.get('A'):
        continue
    status = r['L']
    assert status in ('<LD', '<LQ', 'VAL')
    assert (r.get('M') in (None, '')) == (status != 'VAL')
    assert 0 < F(r['N']) <= F(r['O'])
    if status == 'VAL':
        assert F(r['M']) >= F(r['O'])
    eati[status] += 1
assert eati == {'<LD': 63350, '<LQ': 583, 'VAL': 179}
domains = {}
for field in ['LB_tested', 'UB_tested']:
    selected = [r for r in columns if Decimal(r[field]) > 0]
    factors = sorted(F(int(r['n_tested']), 1193) for r in selected)
    median = (factors[(len(factors)-1)//2] + factors[len(factors)//2]) / 2
    wrong = 'WRONG_LB_all_rows' if field.startswith('LB') else 'WRONG_UB_all_rows'
    for r in selected:
        assert abs(Decimal(r[wrong]) - Decimal(r[field]) * Decimal(r['n_tested']) / 1193) < Decimal('1e-24')
    domains[field] = {'positive_columns': len(selected), 'median': str(median)}
assert domains == {'LB_tested': {'positive_columns': 58, 'median': '683/1193'}, 'UB_tested': {'positive_columns': 322, 'median': '410/1193'}}
assert all(sha(Path(r['path'])) == r['sha256'] for r in receipt['sources'])
out = {'checked_at': datetime.now(timezone.utc).isoformat(), 'v26_delivery_files_preserved': len(records), 'frozen_files_preserved': len(freeze),
       'raw_source_hashes_preserved': len(receipt['sources']), 'EAT2_source_statuses': dict(all_status), 'EAT2_group_chemical_denominators_checked': len(matrix),
       'EATi_source_statuses': dict(eati), 'positive_endpoint_domains': domains, 'vegetable_median_factor': '255/267',
       'boundary': 'Internal computational replay; same archived sources and reused XML parser, not independent assessor or external validation.',
       'code_sha256': sha(Path(__file__)), 'reused_XML_reader_sha256': sha(reader), 'new_exposure_calculations': 0}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps(out, ensure_ascii=False, indent=2))
