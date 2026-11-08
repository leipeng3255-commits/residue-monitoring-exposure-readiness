"""Retrospective bounded extension, not a new exposure model. See v31 protocol."""
import collections as C
import csv
import hashlib
import io
import json
import math
import zipfile
from fractions import Fraction as F
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / '00_admin/paths.yaml').read_text())
OUT = Path(CFG['intermediate_data_root']) / 'depth_extension_v31_20261014'
BASE = ROOT / '10_submission/最终投稿材料_v30_31面板科学图修订_文件夹版/03_可复现数据与代码_NOT_DIRECT_UPLOAD'
DIAG = Path(CFG['outputs_root']) / 'diagnostics'

def sha(p):
    with p.open('rb') as h: return hashlib.file_digest(h, 'sha256').hexdigest()

def read(p):
    with p.open(encoding='utf-8-sig', newline='') as h: return list(csv.DictReader(h))

def write(name, rows):
    assert rows, name
    with (OUT / name).open('x', newline='') as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def jwrite(name, value):
    with (OUT / name).open('x') as h: json.dump(value, h, indent=2, ensure_ascii=False)

def numeric(s):
    try:
        v=F(s)
        return v if v >= 0 else None
    except (ValueError, ZeroDivisionError, TypeError): return None

def direction(lo, hi):
    return 'CZ_ABOVE_DE' if lo > 1 else 'CZ_BELOW_DE' if hi < 1 else 'UNRESOLVED'

FIELDS = ['sampId_A','resId_A','paramCode.base.param','paramType','resType','resUnit','resVal',
          'resLOQ','resLOD','exprResType','sampMatCode.base.building','anMatCode.base.building',
          'sampMatCode.prod','anMatCode.prod','sampMatCode.process','anMatCode.process',
          'sampCountry','origCountry','procCountry','sampY','sampM','sampD','progType','sampStrategy']

def extract():
    manifest=read(ROOT/'00_admin/download_manifest.csv')
    de_receipt=json.loads((ROOT/'00_admin/efsa_de_full_reconciliation_receipt_20261008.json').read_text())
    de=next(r for r in de_receipt['national_profiles'] if r['year']=='2022')
    cz=next(r for r in manifest if r['original_filename']=='MOPER_ALL_DATA_SSD2_2022_CZ.ZIP')
    entries={'CZ':dict(path=cz['local_file_path'],sha256=cz['sha256'],bytes=int(cz['bytes'])),
             'DE':{k:de[k] for k in ('path','sha256','bytes')}}
    source_report=[]
    for market,e in entries.items():
        p=Path(e['path']); assert p.is_relative_to(Path(CFG['raw_data_root']))
        assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256']
        dest=OUT/f'{market}_2022_all_declared_tomato_macp.csv'
        count=selected=0
        with dest.open('x',newline='') as target, zipfile.ZipFile(p) as z:
            w=csv.writer(target);w.writerow(FIELDS)
            members=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(members)==1
            with z.open(members[0]) as b, io.TextIOWrapper(b,encoding='utf-8-sig',newline='') as h:
                r=csv.reader(h);header=next(r); ids={k:header.index(k) for k in FIELDS}
                for row in r:
                    count+=1
                    if (row[ids['sampY']]=='2022' and row[ids['sampCountry']]==market
                        and row[ids['sampMatCode.base.building']]=='A0DMX'
                        and row[ids['progType']]=='K009A' and row[ids['sampStrategy']]=='ST10A'):
                        w.writerow([row[ids[k]] for k in FIELDS]);selected+=1
        assert sha(p)==e['sha256']
        source_report.append(dict(market=market,**e,rows_scanned=count,scoped_rows=selected,
                                  crc='PASS_EOF',extract=dest.name,extract_sha256=sha(dest)))
        print(json.dumps(source_report[-1]),flush=True)
    jwrite('extraction_receipt.json',source_report)

def run():
    assert Path(CFG['data_root']).is_dir()
    OUT.mkdir(parents=True,exist_ok=True)
    if not (OUT/'extraction_receipt.json').exists(): extract()
    sources=json.loads((OUT/'extraction_receipt.json').read_text())
    scoped=[]
    for s in sources:
        p=OUT/s['extract'];assert sha(p)==s['extract_sha256'];scoped.extend(read(p))
    mappings=json.loads((DIAG/'organic_pair_identification_20261008/source_definition_correspondence.json').read_text())
    mapping={r['active_substance_code']:r for r in mappings}
    mapping['RF-00004675-PAR']={'monitoring_definition_codes':'RF-0225-001-PPP',
        'active_substance':'Phosphonic acid','conversion_factor':'0.75',
        'source_document':'https://doi.org/10.2903/j.efsa.2021.6782'}
    # P005A is required below. The alternative abamectin code denotes overlapping
    # component rows in this source and is never added to its complete aggregate.
    ready=read(DIAG/'efsa_scientific_exposure_admission/macp_37_execution_readiness_20260921_v6.csv')
    admitted=[r for r in ready if r['residue_definition_status'] in ('RD_EXACT','RD_CONVERSION_AVAILABLE')]
    baseline={(r['occurrence_country'],r['pesticide']):r for r in read(BASE/'tables/cell_diagnostics.csv')}
    assert len(admitted)==19
    index=C.defaultdict(list)
    for r in scoped:index[(r['sampCountry'],r['paramCode.base.param'],r['paramType'])].append(r)
    lot_rows=[]; summaries=[]; deletions=[]; groups={}; bindings=[]
    for r in admitted:
        market,active=r['reporting_country'],r['active_substance_code']
        name=r['active_substance'].split(' (')[0].lower()
        unit=f'{market}|2022|A0DMX|K009A|ST10A|{active}'
        mp=mapping[active]; codes=mp['monitoring_definition_codes'].split('|')
        if name=='abamectin': codes=['RF-00004655-PAR']
        rows=[x for code in codes for x in index[(market,code,'P005A')]]
        assert len(rows)==len({x['sampId_A'] for x in rows})==int(r['sample_n']), (name,len(rows),r['sample_n'])
        assert len(rows)==len({x['resId_A'] for x in rows})
        assert all(x['resUnit']=='G061A' and x['exprResType']=='B001A'
                   and x['resType'] in ('VAL','LOQ') for x in rows)
        assert sum(x['resType']=='VAL' for x in rows)==int(r['quantified_n'])
        factor=F(r['conversion_factor'] or '1')
        lows=[numeric(x['resVal']) if x['resType']=='VAL' else F(0) for x in rows]
        highs=[numeric(x['resVal']) if x['resType']=='VAL' else numeric(x['resLOQ']) for x in rows]
        assert all(a is not None and b is not None and 0<=a<=b for a,b in zip(lows,highs))
        n=len(rows); sl,su=sum(lows),sum(highs)
        for actual,field in [(sl/n,'monitoring_mean_lb_mg_kg'),(su/n,'monitoring_mean_ub_mg_kg'),
                            (factor*sl/n,'risk_assessment_mean_lb_mg_kg'),(factor*su/n,'risk_assessment_mean_ub_mg_kg')]:
            assert math.isclose(float(actual),float(r[field]),rel_tol=1e-11,abs_tol=1e-14),(name,field)
        b=baseline[(market,name)]
        assert int(b['sample_n'])==n and int(b['quantified_n'])==int(r['quantified_n'])
        assert all(math.isclose(float(v),float(b[k]),rel_tol=1e-11,abs_tol=1e-14) for v,k in
                   [(factor*sl/n,'occurrence_LB'),(factor*su/n,'occurrence_UB')])
        for x,l,u in zip(rows,lows,highs):
            lot_rows.append(dict(unit_id=unit,market=market,pesticide=name,active_code=active,
                sample_id=x['sampId_A'],result_id=x['resId_A'],monitoring_code=x['paramCode.base.param'],
                result_type=x['resType'],value=x['resVal'],loq=x['resLOQ'],factor=str(factor),
                monitoring_lower=str(l),monitoring_upper=str(u),origin=x['origCountry'],month=x['sampM']))
            lo,hi=factor*(sl-l)/(n-1),factor*(su-u)/(n-1)
            deletions.append(dict(unit_id=unit,market=market,pesticide=name,omitted_sample_id=x['sampId_A'],
                lower=float(lo),upper=float(hi),lower_relative=float(lo/(factor*sl/n)) if sl else '',
                upper_relative=float(hi/(factor*su/n)) if su else ''))
        dd=[x for x in deletions if x['unit_id']==unit]
        summaries.append(dict(unit_id=unit,market=market,pesticide=name,n=n,quantified_n=int(r['quantified_n']),
            factor=float(factor),lower=float(factor*sl/n),upper=float(factor*su/n),
            censor_width_fraction=float((su-sl)/su) if su else '',
            largest_quantified_share=float(max(lows)/sl) if sl else '',
            deletion_lower_min=min(x['lower'] for x in dd),deletion_lower_max=max(x['lower'] for x in dd),
            deletion_upper_min=min(x['upper'] for x in dd),deletion_upper_max=max(x['upper'] for x in dd),
            source_sample_ids_sha256=hashlib.sha256('\n'.join(sorted(x['sampId_A'] for x in rows)).encode()).hexdigest()))
        groups[(market,name)]=(rows,lows,highs,factor)
        bindings.append(dict(unit_id=unit,monitoring_codes='|'.join(codes),parameter_type='P005A',factor=str(factor),
            source=mp['source_document'],definition_version='20260921_v6',
            identity_limit='Fresh raw reconstruction; counts/means and published mappings reconciled. No claim of a missing historical row-level manifest.'))
    ratios=[]
    for name in sorted({n for m,n in groups if ('CZ',n) in groups and ('DE',n) in groups}):
        means={m:(sum(groups[(m,name)][1])/len(groups[(m,name)][0]),sum(groups[(m,name)][2])/len(groups[(m,name)][0])) for m in ('CZ','DE')}
        original=(means['CZ'][0]/means['DE'][1],means['CZ'][1]/means['DE'][0])
        for market in ('CZ','DE'):
            rows,lo,hi,factor=groups[(market,name)];assert factor==1
            for i,r in enumerate(rows):
                updated=dict(means);updated[market]=((sum(lo)-lo[i])/(len(rows)-1),(sum(hi)-hi[i])/(len(rows)-1))
                a,b=updated['CZ'][0]/updated['DE'][1],updated['CZ'][1]/updated['DE'][0]
                ratios.append(dict(pesticide=name,omitted_market=market,omitted_sample_id=r['sampId_A'],
                    original_lower=float(original[0]),original_upper=float(original[1]),
                    original_decision=direction(*original),lower=float(a),upper=float(b),decision=direction(a,b)))
    inventory=[]
    for (market,code,typ),rows in sorted(index.items()):
        kinds=C.Counter(r['resType'] for r in rows)
        nums=[r for r in rows if ((r['resType']=='VAL' and numeric(r['resVal']) is not None) or
            (r['resType']=='LOQ' and numeric(r['resLOQ']) is not None) or
            (r['resType']=='LOD' and numeric(r['resLOD']) is not None))]
        n=len(rows);q=kinds['VAL']; ids={r['sampId_A'] for r in rows}
        state='ALL_REPORTED_BELOW_LIMIT' if kinds['LOQ']+kinds['LOD']==n else 'HAS_VAL' if q else 'OTHER_TYPES_ONLY'
        inventory.append(dict(market=market,year='2022',commodity='A0DMX',programme='K009A/ST10A',
            monitoring_code=code,parameter_type=typ,rows=n,samples=len(ids),quantified_records=q,
            loq_records=kinds['LOQ'],lod_records=kinds['LOD'],other_records=n-q-kinds['LOQ']-kinds['LOD'],
            state=state,numeric_typed_records=len(nums),sample_code_extra_rows=n-len(ids),
            units='|'.join(sorted({r['resUnit'] for r in rows})),expressions='|'.join(sorted({r['exprResType'] for r in rows})),
            chemical_risk_admission='NOT_ASSIGNED_BY_CODE_INVENTORY',
            historical_support_rule_met=(len(ids)>=10 and q>=3)))
    overlap=[]
    # Unique sampled lots, not analytical rows or 88 repeated dietary profiles.
    common='azoxystrobin'; meta={}
    for m in ('CZ','DE'):
        meta[m]=C.Counter((r['sampM'] or 'UNKNOWN',r['origCountry'] or 'UNKNOWN') for r in groups[(m,common)][0])
    for key in sorted(set(meta['CZ'])|set(meta['DE'])):
        overlap.append(dict(month=key[0],origin=key[1],CZ=meta['CZ'][key],DE=meta['DE'][key],
                            shared_category=bool(meta['CZ'][key] and meta['DE'][key])))
    for name,rs in [('reconstructed_19_lot_rows.csv',lot_rows),('all19_influence_summary.csv',summaries),
                    ('all19_single_lot_deletions.csv',deletions),('shared_ratio_deletions.csv',ratios),
                    ('all_declared_code_inventory.csv',inventory),('shared_sample_metadata.csv',overlap),('source_bindings.csv',bindings)]:write(name,rs)
    jwrite('analysis_receipt.json',dict(scope='RETROSPECTIVE_FINITE_RECORD_EXTENSION_NOT_NEW_EXPOSURE',
        rows_reconstructed=len(lot_rows),units=19,deletions=len(deletions),ratio_deletions=len(ratios),
        distinct_sample_ids=len({(r['market'],r['sample_id']) for r in lot_rows}),
        inventory_units=len(inventory),inventory_rows=sum(r['rows'] for r in inventory),
        inventory_states=dict(C.Counter(r['state'] for r in inventory)),
        inventory_parameter_types=dict(C.Counter(r['parameter_type'] for r in inventory)),
        source_provenance=sources,protocol_sha256=sha(ROOT/'01_protocol/depth_extension_v31_20261014.md'),
        code_sha256=sha(Path(__file__)),new_exposure_calculations=0,
        outputs=[dict(file=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.glob('*.csv'))]))
    print((OUT/'analysis_receipt.json').read_text(),flush=True)

if __name__=='__main__':run()
