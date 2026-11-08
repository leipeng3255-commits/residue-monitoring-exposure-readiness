"""Prespecified, separate PDP cherry-tomato structural application. No exposure."""
import collections,csv,hashlib,io,json,zipfile
from pathlib import Path
import openpyxl
ROOT=Path(__file__).resolve().parents[2]
cfg={k.strip():json.loads(v.strip()) for l in (ROOT/'00_admin/paths.yaml').read_text().splitlines() if l and not l.startswith('#') for k,v in [l.split(':',1)]}
archive=Path(cfg['raw_data_root'])/'other/2024PDPDatabase.zip'
out=ROOT/'00_admin/independent_source_application_20260928';out.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protocol=ROOT/'01_protocol/independent_source_application_20260928.md'
receipt={'protocol_sha256':sha(protocol),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'selected_commodity':'CT','selection':'Cherry Tomatoes; fresh per official dictionary, raw-tomato target selected before result inspection','independence':'Separate programme and year, previously inspected source, not blinded or independent-assessor validation'}
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 receipt['zip_crc']='PASS'
 w=openpyxl.load_workbook(io.BytesIO(z.read('PDP ReferenceTables 2024.xlsx')),read_only=True,data_only=True)
 refs={n:[list(r) for r in w[n].values] for n in ['Commodity','Commod Type','Mean','Annotate','Con Unit']}
 assert any(r[0]=='CT' and r[1]=='Cherry Tomatoes' for r in refs['Commodity'])
 (out/'official_code_evidence.json').write_text(json.dumps(refs,indent=2,default=str))
 samples={};sample_duplicates=0
 for r in csv.reader(io.TextIOWrapper(z.open('PDP24Samples.txt')),delimiter='|'):
  assert len(r)==18
  if r[0] in samples:sample_duplicates+=1
  samples[r[0]]=r
 selected={k:v for k,v in samples.items() if v[6]=='CT'}
 flags=collections.Counter();annotations=collections.Counter();units=collections.Counter();keys=collections.Counter();panels=collections.defaultdict(set);analytes=collections.defaultdict(lambda:collections.Counter());errors=collections.Counter()
 total=0
 for r in csv.reader(io.TextIOWrapper(z.open('PDP24Results.txt')),delimiter='|'):
  assert len(r)==16
  if r[1]!='CT':continue
  total+=1;k=r[0];p=r[4];flag=r[13].strip();conc=r[6].strip();lod=r[7].strip()
  flags[flag]+=1;annotations[r[11].strip()]+=1;units[r[8]]+=1;keys[(k,p)]+=1;panels[k].add(p);a=analytes[p];a['rows']+=1;a['flag_'+flag]+=1
  if k not in samples:errors['orphan_sample']+=1
  elif samples[k][6]!=r[1] or samples[k][12]!=r[2]:errors['commodity_or_form_mismatch']+=1
  if not lod:errors['missing_lod']+=1
  else:
   try:
    if float(lod)<=0:errors['nonpositive_lod']+=1
   except ValueError:errors['invalid_lod']+=1
  if not conc:a['blank_concentration']+=1
  else:
   try:float(conc)
   except ValueError:errors['invalid_concentration']+=1
  if flag=='ND' and conc:errors['ND_with_nonblank_concentration']+=1
 unique_per_analyte=collections.Counter(p for k,p in keys)
 for p,a in analytes.items():a['tested_sample_keys']=unique_per_analyte[p]
 receipt.update({'sample_records_all':len(samples),'duplicate_sample_keys_all':sample_duplicates,'selected_samples':len(selected),'selected_result_rows':total,'analyte_codes':len(analytes),'result_flags':dict(flags),'annotation_codes':dict(annotations),'concentration_units':dict(units),'duplicate_sample_analyte_keys':sum(n>1 for n in keys.values()),'extra_rows_on_duplicate_keys':sum(n-1 for n in keys.values()),'samples_without_any_result':len(set(selected)-set(panels)),'per_sample_analyte_count_min':min(map(len,panels.values())),'per_sample_analyte_count_max':max(map(len,panels.values())),'tested_samples_per_analyte_min':min(unique_per_analyte.values()),'tested_samples_per_analyte_max':max(unique_per_analyte.values()),'structural_errors':dict(errors)})
 fields=sorted({k for a in analytes.values() for k in a})
 with (out/'analyte_support.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=['analyte_code']+fields);writer.writeheader()
  for p,a in sorted(analytes.items()):writer.writerow({'analyte_code':p,**a})
receipt['archive_sha256_after']=sha(archive);assert receipt['archive_sha256']==receipt['archive_sha256_after']
(out/'structural_audit.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
