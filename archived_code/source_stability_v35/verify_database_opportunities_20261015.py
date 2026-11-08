"""Separate text/XML readers for the bounded feasibility audit; no exposure model."""
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
from decimal import Decimal
from datetime import datetime, timezone
import hashlib, io, json, re, statistics, zipfile, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CFG = {k:json.loads(v.strip()) for k,v in (line.split(':',1) for line in
       (ROOT/'00_admin/paths.yaml').read_text().splitlines() if re.match(r'^[a-z_]+:\s*"',line))}
OUT = Path(CFG['outputs_root'])/'diagnostics/depth_feasibility_20261015'
TARGET = OUT/'separate_reader_verification.json'
assert not TARGET.exists()
SOURCES = json.loads((OUT/'source_provenance.json').read_text())
N = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def xml_rows(data, name):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in si.iter('{'+N['s']+'}t'))
                    for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        sheet=next(s for s in wb.find('s:sheets',N) if s.attrib['name']==name)
        rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rel=next(r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if r.attrib['Id']==rid)
        target=rel.attrib['Target']
        target=target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl')/target)
        rows={}
        for row in ET.fromstring(z.read(target)).find('s:sheetData',N):
            cells={}
            for c in row:
                column=re.match(r'[A-Z]+',c.attrib['r'])[0]
                value=c.find('s:v',N); value=value.text if value is not None else None
                kind=c.attrib.get('t')
                if kind=='s': value=shared[int(value)]
                elif kind=='inlineStr': value=''.join(t.text or '' for t in c.findall('.//s:t',N))
                elif value is not None and kind not in ('str','e'): value=Decimal(value)
                cells[column]=value
            rows[int(row.attrib['r'])]=cells
    return rows

# Independently split source text; retain Decimal LODs and keyed assay coverage.
expected=json.loads((OUT/'pdp_tomato_analyte_profiles.json').read_text())
expected={(r['year'],r['pesticide_code']):r for r in expected}
sample_frames=[]; selected=defaultdict(dict)
for src in SOURCES:
    if not re.match(r'202[0-4]PDPDatabase.zip',src['filename']): continue
    year=int(src['filename'][:4])
    with zipfile.ZipFile(src['path']) as z:
        sample=next(n for n in z.namelist() if 'Samples' in n and n.endswith('.txt'))
        rows=[line.split('|') for line in z.read(sample).decode('utf-8-sig').splitlines()]
        frame=Counter((r[6],r[12]) for r in rows)
        sample_frames.append(dict(year=year,n=len(rows),frames=frame))
        if year not in (2022,2023): continue
        ids={r[0] for r in rows if (r[6],r[12])==('TO','FR')}
        result=next(n for n in z.namelist() if 'Results' in n and n.endswith('.txt'))
        d=defaultdict(lambda:dict(ids=set(),lod=[],n=0))
        with z.open(result) as handle:
            for raw in handle:
                r=raw.decode('utf-8-sig').rstrip('\r\n').split('|')
                if r[0] not in ids: continue
                assert (r[1],r[2])==('TO','FR')
                a=d[r[4]]; a['ids'].add(r[0]); a['lod'].append(Decimal(r[7])); a['n']+=1
        for code,a in d.items():
            e=expected[year,code]
            assert a['n']==e['result_rows'] and len(a['ids'])==e['tested_samples']
            assert len(ids)==e['sample_frame']
            assert min(a['lod'])==Decimal(str(e['lod_min']))
            assert max(a['lod'])==Decimal(str(e['lod_max']))
            assert statistics.median(a['lod'])==Decimal(str(e['lod_median']))
        selected[year]=d
profiles=json.loads((OUT/'pdp_sample_and_tomato_profiles.json').read_text())
for a,b in zip(sample_frames,profiles):
    assert a['year']==b['year'] and a['n']==b['sample_records']
    assert a['frames']==Counter({(r['commodity'],r['form']):r['n'] for r in b['counts']})
common=set(selected[2022])&set(selected[2023])
assert len(common)==362
assert sum(statistics.median(selected[2022][k]['lod'])!=statistics.median(selected[2023][k]['lod']) for k in common)==31
print('Separate PDP reader passed',flush=True)

# Recipe comparison via worksheet XML, without openpyxl or previous recipe groups.
aus_src=next(s for s in SOURCES if s['filename'].startswith('AUSNUT'))
with zipfile.ZipFile(aus_src['path']) as z:
    def data(suffix): return z.read(next(n for n in z.namelist() if n.endswith(suffix)))
    groups={}; counts={}
    for key,file,sheet in [('nutrient','Food nutrient recipes.xlsx','Food nutrient recipes'),
                           ('adg','Australian Dietary Guidelines recipes.xlsx','ADG Recipes')]:
        rows=xml_rows(data(file),sheet); group=defaultdict(list)
        for i,r in rows.items():
            if i<4 or r.get('A') is None: continue
            group[r['A']].append(tuple(r.get(c) for c in ('E','F','H','D')))
        groups[key]=group; counts[key]=sum(map(len,group.values()))
    shared=set(groups['nutrient'])&set(groups['adg'])
    assert len(shared)==1534
    assert all(Counter(groups['nutrient'][k])==Counter(groups['adg'][k]) for k in shared)
    aus=json.loads((OUT/'ausnut_recipe_feasibility.json').read_text())
    assert counts==aus['recipe_rows']
    assert {k:len(v) for k,v in groups.items()}==aus['recipe_food_counts']
    match=xml_rows(data('Matching file.xlsx'),'TAB A - Matching file')
    mapped=[r for i,r in match.items() if i>=5 and r.get('B') is not None]
    assert len(mapped)==3741 and sum(r.get('D') is None for r in mapped)==1059
print('Separate AUSNUT XML reader passed',flush=True)

# Preserve duplicate XML rows and verify case-only key differences separately.
nz_expected=json.loads((OUT/'nz_quarter_structure.json').read_text())
nz={};nz_checks=[]
for src in SOURCES:
    if 'new_zealand_mpi_total_diet_study' not in src['path']: continue
    q=Path(src['path']).parent.name[-2:]
    rows=xml_rows(Path(src['path']).read_bytes(),'Table 1.1 All results')
    header=rows[1]; cols=[c for c,v in header.items() if str(v).startswith('Quarter')]
    unit_col=next(c for c,v in header.items() if v=='Unit')
    g=defaultdict(list)
    for i,r in rows.items():
        if i<=2 or not r.get('A') or not r.get('C'): continue
        k=(r['A'],r.get('B'),r['C'],r.get(unit_col))
        g[k].append(dict(row=i,values={header[c]:r.get(c) for c in cols}))
    e=next(p for p in nz_expected['profiles'] if p['quarter_label']==q)
    assert sum(map(len,g.values()))==e['source_data_rows'] and len(g)==e['distinct_keys']
    assert sum(len(v)>1 for v in g.values())==e['duplicate_key_groups']
    nz[q]={k:v[0]['values'] for k,v in g.items() if len(v)==1}
for earlier,later in [('Q1','Q3'),('Q2','Q4')]:
    a,b=nz[earlier],nz[later]
    exact=set(a)&set(b)
    differences=sum(a[k][c]!=b[k][c] for k in exact for c in a[k])
    e=next(v for v in nz_expected['repeated_quarter_checks'] if v['earlier']==earlier)
    assert len(exact)==e['overlapping_row_keys'] and differences==e['changed_repeated_values']
    # Diagnostic only: casefold food label, preserving chemical/group/unit exactly.
    def canon(k): return (k[0].casefold(),)+k[1:]
    aa={canon(k):v for k,v in a.items()};bb={canon(k):v for k,v in b.items()}
    assert len(aa)==len(a) and len(bb)==len(b)
    shared=set(aa)&set(bb)
    changes=[dict(key=k,column=c,earlier=aa[k][c],later=bb[k][c])
             for k in sorted(shared) for c in aa[k] if aa[k][c]!=bb[k][c]]
    nz_checks.append(dict(earlier=earlier,later=later,
        diagnostic_food_casefold_shared_keys=len(shared),additional_matches_after_casefold=len(shared)-len(exact),
        repeated_cells_compared=sum(len(aa[k]) for k in shared),changed_cells=changes,
        unmatched_earlier_keys=sorted(set(aa)-set(bb)),unmatched_later_keys=sorted(set(bb)-set(aa)),
        diagnostic_only='Casefold is not a general food/chemical equivalence decision. Duplicate identities remain excluded.'))
print('Separate NZ XML reader passed',flush=True)
seal=json.loads((ROOT/'00_admin/delivery_seal_v34.json').read_text());folder=Path(seal['folder'])
assert sha(folder/'file_manifest.json')==seal['manifest_sha256']
delivery=json.loads((folder/'file_manifest.json').read_text())
for r in delivery:
    p=folder/r['path'];assert p.stat().st_size==r['size'] and sha(p)==r['sha256']
for r in SOURCES: assert sha(r['path'])==r['sha256']
result=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
    pdp_years=5,pdp_tomato_analyte_year_profiles=len(expected),pdp_common_codes=362,
    ausnut_shared_recipes_xml_verified=1534,nz_paired_checks=nz_checks,
    selected_raw_files_unchanged=len(SOURCES),sealed_v34_verified=len(delivery),
    script_sha256=sha(__file__),new_exposure_estimates=0,
    scientific_limit='Separately coded computational verification by the same AI-assisted project, not independent scientific or human validation.')
TARGET.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='nz_paired_checks'},ensure_ascii=False,indent=2))
