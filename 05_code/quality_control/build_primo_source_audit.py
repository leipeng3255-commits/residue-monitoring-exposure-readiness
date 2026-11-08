"""Inventory the preserved official source and examples; never execute test consumption."""
import csv
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
paths = {}
for line in (ROOT / '00_admin/paths.yaml').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key, value = line.split(':', 1)
        paths[key.strip()] = Path(value.strip().strip('"'))
receipt = json.loads((ROOT / '00_admin/primo_official_source_receipt.json').read_text())
archive = paths['raw_data_root'] / 'efsa_zenodo/14534478/primo4_4.0.1.tar.gz'
source = paths['intermediate_data_root'] / 'primo4_4_0_1_source_audit/primo4'
out = paths['outputs_root'] / 'diagnostics/primo_source_audit'
out.mkdir(exist_ok=True)
sha = lambda content: hashlib.sha256(content).hexdigest()
assert sha(archive.read_bytes()) == receipt['sha256']
inventory = []
with tarfile.open(archive) as tf:
    for member in tf:
        if not member.isfile():
            continue
        content = tf.extractfile(member).read()
        rel = Path(member.name).relative_to('primo4')
        path = source / rel
        assert path.is_file() and sha(path.read_bytes()) == sha(content), str(rel)
        inventory.append({'file': str(rel), 'bytes': len(content), 'sha256': sha(content)})

def write_csv(name, rows, fields=None):
    buffer = io.StringIO(newline='')
    w = csv.DictWriter(buffer, fieldnames=fields or list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    content = buffer.getvalue().encode('utf-8')
    target = out / name
    if target.exists():
        assert target.read_bytes() == content, f'Existing output differs: {target}'
    else:
        with target.open('xb') as f:
            f.write(content)

write_csv('source_file_inventory.csv', inventory)
pattern = re.compile(r'RPC_STMR|\bSTMR\b|RPC_HR|occurrence|chronic|Excel|validation|\bADI\b|\bRPC\b|consumption', re.I)
hits = []
for path in sorted(source.rglob('*')):
    if not path.is_file() or path.suffix.lower() not in {'.r', '.rd', '.md', '.txt', '.sql'}:
        continue
    function = '<file scope>'
    for n, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
        match = re.match(r'\s*([\w.]+)\s*<-\s*function\b', line)
        if match:
            function = match[1]
        if pattern.search(line):
            rel = str(path.relative_to(source))
            role = 'documentation/test/context'
            interpretation = 'Search hit; interpretation requires surrounding code.'
            if rel == 'R/rpc-tab.R' and 55 <= n <= 65:
                role = 'chronic numeric concentration and automatic label'
                interpretation = 'STMR-valued slot overrides MRL; CF defaults to 1; label is not value provenance.'
            elif rel == 'R/chronic-compute.R' and n <= 223:
                role = 'consumption linkage, dose, subject sum or ADI statistics'
                interpretation = 'Numeric occurrence is combined with intake and body weight; no source-type branch.'
            elif rel.endswith('serverUploadChecks.R') or rel.endswith('serverDataEntry.R'):
                role = 'import and structural/numeric validation'
            hits.append(dict(file=rel,function=function,line_number=n,role=role,scientific_interpretation=interpretation,code=line.strip()))
write_csv('rpc_stmr_code_locations.csv', hits)

def workbook_rows(path, sheet):
    w = load_workbook(path, read_only=True, data_only=True)
    s = w[sheet]
    s.reset_dimensions()
    result = list(s.iter_rows(values_only=True))
    w.close()
    return result

annex = paths['raw_data_root'] / 'efsa_zenodo/13220663'
examples = []
for path in sorted(annex.glob('*.xlsx')):
    if path.name.startswith('._'):
        continue
    w = load_workbook(path, read_only=True, data_only=True)
    for s in w:
        if s.title not in {'OCCURRENCE_RPC', 'OCCURRENCE_RPCD'}:
            continue
        s.reset_dimensions()
        rows = list(s.iter_rows(values_only=True))
        if not rows:
            continue
        header = rows[0]
        for rown, row in enumerate(rows[1:], 2):
            values = dict(zip(header, row))
            for field in ('RPC_STMR','RPC_MRL','RPC_CF','RPCD_PF','RPCD_CF'):
                value = values.get(field)
                if value is not None:
                    examples.append({'file':path.name,'sheet':s.title,'row':rown,'field':field,'value':value,
                                     'RPC':values.get('RPC_MatrixCode') or values.get('matrixCode_L5'),
                                     'source_if_documented':values.get('RPC_Source') or values.get('RPCD_Source') or ''})
    w.close()
write_csv('official_example_chronic_fields.csv', examples)
c = workbook_rows(annex / 'Annex C - Food consumption surveys considered in the model.xlsx', 'Table C.1')
crows = [dict(zip(c[0], r)) for r in c[1:] if r and r[0] is not None]
m = workbook_rows(source / 'inst/extdata/Survey_mapping.xlsx', 'Survey mapping')
mapped = {r[1] for r in m[1:] if r[1]}
live_path = paths['outputs_root'] / 'diagnostics/primo_forensic/T02_LB_v5_detailed_technical_recovery_20260921.xlsx'
live = workbook_rows(live_path, 'Sheet 1')
live_rows = [dict(zip(live[0],r)) for r in live[1:] if r and r[0] is not None]
write_csv('annex_c_survey_inventory.csv', crows)
write_csv('technical_output_survey_inventory.csv', live_rows)
crows = [r for r in crows if r.get('Survey') and r.get('Country')]
report = {'archive':str(archive),'bytes':archive.stat().st_size,'sha256':receipt['sha256'],
          'release':'4.0-1','release_date':'2024-12-31','source_version':'4.0.1',
          'source_url':receipt['url'],'verified_extracted_files':len(inventory),'search_hits':len(hits),
          'example_field_rows':len(examples),'annex_c_strata':len(crows),
          'annex_c_surveys':len({r['Survey'] for r in crows}), 'annex_c_countries':len({r['Country'] for r in crows}),
          'source_mapping_surveys':len(mapped),'technical_output_rows':len(live_rows),
          'technical_output_columns':live[0], 'annex_c_names_missing_from_source_mapping':sorted({r['Survey'] for r in crows}-mapped)}
with (out/'source_audit_inventory.json').open('x') as f:
    json.dump(report,f,indent=2,ensure_ascii=False)
print(json.dumps(report,indent=2,ensure_ascii=False))
