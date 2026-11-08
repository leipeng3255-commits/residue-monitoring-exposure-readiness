"""Finite source-coverage overlay and question-specific evidence table."""
import collections,csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CFG={k.strip():json.loads(v.strip()) for l in (ROOT/'00_admin/paths.yaml').read_text().splitlines()
     if l and not l.startswith('#') for k,v in [l.split(':',1)]}
OUT=Path(CFG['intermediate_data_root'])/'manuscript_evidence_extension_v22_20261008';OUT.mkdir(exist_ok=False)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(n,rows):
    with (OUT/n).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
old=Path(CFG['processed_data_root'])/'global_surveillance_inventory_2022_context.csv'
context=read(old);assert len(context)==217 and len({r['iso3'] for r in context})==217
meta=Path(CFG['raw_data_root'])/'population/worldbank_countries_20260921.json'
assert sha(meta)=='4bca8777553d4e674df745b0628cbb8bf5efe838ef8f5cb606ad3b15d48b3302'
countries={r['iso2Code']:r for r in json.loads(meta.read_text())[1] if r['region']['id']!='NA'}
rec=json.loads((ROOT/'00_admin/efsa_all_observed_reconciliation_receipt_20261008.json').read_text())
coverage=Path(rec['output_dir'])/'archive_coverage.csv'
record=next(r for r in rec['artifacts'] if r['path']==str(coverage));assert sha(coverage)==record['sha256']
rows=read(coverage);assert len(rows)==98
codes=sorted({r['country'] for r in rows});mapped={c:countries[c]['id'] for c in codes if c!='XI'}
assert len(codes)==33 and len(mapped)==32 and len(set(mapped.values()))==32
geographies=[]
for c in codes:
    selected=[r for r in rows if r['country']==c]
    geographies.append({'source_reporting_code':c,'iso3_context':mapped.get(c,''),
        'geography':countries[c]['name'] if c!='XI' else 'Northern Ireland (regional; not all United Kingdom)',
        'years':'|'.join(sorted({r['year'] for r in selected})), 'archived_files':len(selected),
        'analytical_records_read':sum(int(r['rows_scanned']) for r in selected),
        'scope':'ARCHIVE_RECORD_RECONCILIATION_ONLY_FIXED_CANDIDATES','exposure_readiness':'NOT_CERTIFIED_SOURCE_WIDE'})
write('reconciled_reporting_geographies.csv',geographies)
overlay=[]
for r in context:
    codes_here=[c for c,v in mapped.items() if v==r['iso3']]
    overlay.append({'iso3':r['iso3'],'country':r['country'],'context_year':r['year'],
        'legacy_dated_public_class':r['audited_public_data_class'],
        'efsa_reporting_archive_reconciliation':'OBSERVED_RECONCILED' if codes_here else 'NOT_ASSESSED_BY_THIS_EFSA_OVERLAY',
        'source_reporting_codes':'|'.join(codes_here),
        'country_wide_exposure_estimate':'NOT_INFERRED','zero_exposure_imputation':'PROHIBITED',
        'scope':'BOUNDED_EFSA_OVERLAY_NOT_WORLD_MONITORING_CENSUS'})
assert sum(r['efsa_reporting_archive_reconciliation']=='OBSERVED_RECONCILED' for r in overlay)==32
write('global_context_bounded_overlay_20261008.csv',overlay)
base=Path(CFG['intermediate_data_root'])/'manuscript_data_reuse_audit_20261008'
efsa=json.loads((base/'efsa_reuse_profile.json').read_text());pdp=json.loads((base/'pdp_scope_profile.json').read_text())
pf=json.loads((base/'processing_reuse_profile.json').read_text());bw=json.loads((base/'bw_context_source.json').read_text())
assert sha(Path(bw['local_path']))==bw['sha256']
evidence=[
 {'source':'EFSA fixed five-crop mapping','question':'Are censoring limits available for these mapped records?',
  'grain':'country-year-sample-reported expression mapping key','count':'493 held mapping keys','finding':'AT450 DE8 IT1 NO34',
  'permitted':'Retain source-specific hold keys','not_permitted':'Use493 as a worldwide missingness rate'},
 {'source':'DE2022 MACP tomato paired set','question':'Does censoring determine an organic/nonorganic sampled-mean contrast?',
  'grain':'15 chemicals sharing214 lots; analyte panels unequal','count':'15 complete-expression comparisons',
  'finding':'All15 difference intervals contain0; all15 ratio intervals contain1','permitted':'Descriptive source-specific concentration bounds',
  'not_permitted':'Causal organic coefficient, national effect or new exposure'},
 {'source':'USDA PDP2024 CT','question':'Does the source identify the general raw-tomato target and production comparison?',
  'grain':'529 cherry/grape-tomato samples','count':'PO37 NC488 PD4; April-December',
  'finding':'Small-tomato commodity and source claims do not establish certified conventional comparator or complete-year general-tomato diet',
  'permitted':'A separately qualified future small-tomato assessment','not_permitted':'Replace general-tomato input; relabel NC/PD conventional'},
 {'source':'EFSA processing database v5','question':'Are factors compatible with the current raw RPC target?',
  'grain':'23 selected median factors;86 trials','count':'19/23 medians reliable;79/86 trials acceptable',
  'finding':'All23 not applied to current general raw-tomato target;1 preparation-code inconsistency retained',
  'permitted':'Evaluate chemical-food-treatment-specific prepared-food targets separately',
  'not_permitted':'Assume all factors unusable or all processing factors equal1'},
 {'source':'Baden-Wuerttemberg2025 organic monitoring','question':'Does group selection change the reported concentration summary?',
  'grain':'Regional vegetable-group multi-pesticide summary;PDFp31','count':'Organic0.008 vs0.003 mg/kg; nonorganic0.58 mg/kg',
  'finding':'Organic label exclusion changes the target group; nonorganic aggregate excludes phosphonic acid and bromide',
  'permitted':'Label-selection and aggregation cautionary case','not_permitted':'Chemical-specific/global causal organic conversion ratio'},
 {'source':'FAOSTAT organic land2022','question':'What does the global organic variable measure?',
  'grain':'ISO3-year-item-element-unit','count':'483 rows;168 geographies;159 match217 context regions',
  'finding':'Organic area/share and certified area are different measures; units include1000ha andpercent',
  'permitted':'Agricultural context','not_permitted':'Organic vegetable intake or vegetable-market replacement fraction'},
 {'source':'EFSA2022-2024 archived-record overlay','question':'Where were original analytical archives reconciled?',
  'grain':'98 reporting-geography-year archives','count':'32 exact WDI geographies plusNorthern Ireland regional appendix',
  'finding':'This finite overlay updates availability evidence, not source-wide quantitative admission',
  'permitted':'Dated source coverage and next-audit priorities','not_permitted':'WholeUK coverage fromXI; global gap proportion or zero exposure'}]
write('question_specific_existing_evidence.csv',evidence)
receipt={'coverage_archives':98,'reporting_regions':33,'exact_context_regions':32,'regional_XI_not_mapped_to_GBR':True,
 'context_regions':217,'not_assessed_by_this_efsa_overlay':185,'world_monitoring_gap_fraction':'NOT_ESTIMATED',
 'input_hashes':{str(p):sha(p) for p in [meta,old,coverage,base/'efsa_reuse_profile.json',base/'pdp_scope_profile.json',base/'processing_reuse_profile.json',base/'bw_context_source.json']},
 'new_exposure_units':0,'outputs':[{'name':p.name,'sha256':sha(p)} for p in OUT.iterdir() if p.is_file() and not p.name.startswith('.')]}
with (OUT/'run_receipt.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(json.dumps({k:receipt[k] for k in ['exact_context_regions','reporting_regions','new_exposure_units']}))
