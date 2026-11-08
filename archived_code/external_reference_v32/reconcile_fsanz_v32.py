"""Complete-block, conditional printed-summary reconciliation; no exposure estimate."""
import csv,hashlib,json,re,subprocess
from pathlib import Path
from fractions import Fraction as F
import yaml
ROOT=Path(__file__).resolve().parents[2];CFG=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(CFG['intermediate_data_root'])/'external_reference_v32_20261014'
manifest=json.loads((OUT/'probe_manifest.json').read_text())
src=next(r for r in manifest if Path(r['path']).name=='25th_ATDS_appendices.pdf')
assert hashlib.sha256(Path(src['path']).read_bytes()).hexdigest()==src['sha256']
text=Path(src['text']).read_text();pages=text.split('\f')
pattern=re.compile(r'^(.*?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+(?:\.\d+)?)\s+(<LOR|\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$')
rows=[];nil=[];pending=[];state=None;carry='';pagecounts={}
for pi,page in enumerate(pages,1):
    if re.search(r'Table A .*document\.\.8:',page):current='A3.8'
    elif re.search(r'Table A .*document\.\.9:',page):current='A3.9'
    else:continue
    if state!=current:carry='';state=current
    pagecounts[pi]=0
    lines=page.splitlines()
    for li,line in enumerate(lines):
        m=pattern.match(line)
        if not m:
            if 'Nil detects' in line:
                nil.append(dict(table=current,page=pi,text=line.strip(),food=line.split('Nil detects')[0].strip()))
            continue
        prefix=m[1];cols=re.split(r'\s{2,}',prefix.strip()) if prefix.strip() else []
        # Positional columns are used only for identity; numeric strings are unmodified.
        if current=='A3.8':left=prefix[:34].strip();right=prefix[34:].strip()
        else:left=prefix[:29].strip();right=prefix[29:].strip()
        if left:carry=left
        if not right:
            pending.append(dict(table=current,page=pi,line=line,reason='multiline second label'))
            if current=='A3.9':
                previous=lines[li-1];left2=previous[:29].strip()
                if left2:carry=left2
                right=previous[29:].strip()
                if li+1<len(lines) and 'single grain or mixed' in lines[li+1]:right+=' '+lines[li+1][29:].strip()
        if current=='A3.9' and right=='Fish portions, frozen from' and li+1<len(lines) and 'supermarket' in lines[li+1]:
            right+=' supermarket'
            pending.append(dict(table=current,page=pi,line=line,reason='fish food label continuation retained'))
        food,chem=(carry,right) if current=='A3.8' else (right,carry)
        n,d,pct,mean,mn,mx=m.group(2,3,4,5,6,7)
        rows.append(dict(table=current,page=pi,row_on_page=pagecounts[pi]+1,food=food,chemical=chem,n=int(n),detects=int(d),pct=pct,mean=mean,minimum=mn,maximum=mx,source_line=line))
        pagecounts[pi]+=1
def write(name,data):
    if not data:return
    with (OUT/name).open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
write('fsanz_printed_rows.csv',rows);write('fsanz_nil_detects.csv',nil)
(OUT/'fsanz_parse_final.json').write_text(json.dumps(dict(rows=len(rows),by_table={t:sum(r['table']==t for r in rows) for t in ['A3.8','A3.9']},pagecounts=pagecounts,multiline_repairs=pending),indent=2))
def norm(s):
    # Remove page-continuation tokens, not chemical/food-form qualifiers.
    s=re.sub(r'\s*\((?:continued|cont[’\x27]d)\)','',s,flags=re.I)
    return re.sub(r'[^a-z0-9]','',s.lower().replace('&','and'))
a={norm(r['food'])+'|'+norm(r['chemical']):r for r in rows if r['table']=='A3.8'}
b={norm(r['food'])+'|'+norm(r['chemical']):r for r in rows if r['table']=='A3.9'}
assert len(a)==174 and len(b)==174
unmatched=[dict(r,disposition='IDENTITY_OR_FOOD_FORM_NOT_AUTOMATICALLY_EQUIVALENT') for d,other in [(a,b),(b,a)] for k,r in d.items() if k not in other]
write('fsanz_unmatched_identities.csv',unmatched)
comparison=[]
for k in sorted(a.keys()&b.keys()):
    x,y=a[k],b[k]
    for f in ['n','detects','pct','mean','minimum','maximum']:
        comparison.append(dict(key=k,food=x['food'],chemical=x['chemical'],page_A8=x['page'],page_A9=y['page'],field=f,A8=x[f],A9=y[f],agrees=str(x[f])==str(y[f])))
write('fsanz_cross_table_fields.csv',comparison)
checks=[]
def cell(s,mult):
    v=F(s);q=F(1,10**len(s.split('.')[1])) if '.' in s else F(1)
    return max(F(0),v-q*mult),v+q*mult
for r in rows:
    for label,mult in [('half_display_unit',F(1,2)),('one_display_unit',F(1))]:
        ml,mu=cell(r['mean'],mult);xl,xu=cell(r['maximum'],mult)
        lower=xl/r['n'];upper=xu*r['detects']/r['n']
        compatible=mu>=lower and ml<=upper
        pct=F(100*r['detects'],r['n']);pctok=abs(F(r['pct'])-pct)<=mult
        checks.append(dict(table=r['table'],page=r['page'],row_on_page=r['row_on_page'],food=r['food'],chemical=r['chemical'],n=r['n'],detects=r['detects'],printed_mean=r['mean'],printed_maximum=r['maximum'],printed_percent=r['pct'],precision_assumption=label,test='single_detect_identity' if r['detects']==1 else 'necessary_mean_bound',conditional_mean_compatible=compatible,conditional_percent_compatible=pctok,mean_interval_lower=str(ml),mean_interval_upper=str(mu),necessary_lower=str(lower),necessary_upper=str(upper),percent_from_printed_n=str(pct)))
write('fsanz_conditional_checks.csv',checks)
bad=[r for r in checks if not r['conditional_mean_compatible'] or not r['conditional_percent_compatible']]
write('fsanz_conditional_discrepancies.csv',bad)
summary=dict(numeric_rows=len(rows),numeric_rows_per_table=174,nil_food_rows=len(nil),matched_identity_pairs=len(a.keys()&b.keys()),unmatched_rows_per_table={t:sum(x['table']==t for x in unmatched) for t in ['A3.8','A3.9']},cross_table_field_differences=[r for r in comparison if not r['agrees']],conditional_checks={})
for label in ['half_display_unit','one_display_unit']:
    subset=[x for x in checks if x['precision_assumption']==label]
    summary['conditional_checks'][label]={t:dict(rows=sum(x['table']==t for x in subset),mean_incompatible=sum(x['table']==t and not x['conditional_mean_compatible'] for x in subset),percent_incompatible=sum(x['table']==t and not x['conditional_percent_compatible'] for x in subset)) for t in ['A3.8','A3.9']}
summary.update(reference_status='PARTIAL_REFERENCE_ELIGIBILITY',external_gold_standard=False,independent_human_validation=False,exposure_units_added=0,limitations='Conditional arithmetic assumes printed n is the relevant unweighted analyte denominator; rounding intervals are analyst assumptions. No reference values repaired. No full framework performance score.')
(OUT/'fsanz_reference_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
