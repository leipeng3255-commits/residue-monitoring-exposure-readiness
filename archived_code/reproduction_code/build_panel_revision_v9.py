"""Lean panel-level figures from saved results; no new exposure estimates."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
P = yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT = ROOT/'08_manuscript/panel_revision_v9'
FIG = OUT/'figures'
FIG.mkdir(parents=True, exist_ok=True)
TABLE = ROOT/'08_manuscript/final_food_control_version/revision_v6/tables'
inputs = []
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    inputs.append({'path':str(p.relative_to(ROOT)), 'sha256':sha(p)})
    return list(csv.DictReader(p.open()))
def js(p):
    inputs.append({'path':str(p.relative_to(ROOT)), 'sha256':sha(p)})
    return json.loads(p.read_text())
freeze = js(ROOT/'00_admin/analysis_freeze_manifest_20260921.json')
for item in freeze['files']:
    assert sha(Path(item['path'])) == item['sha256'], item['path']
cells = read(TABLE/'cell_diagnostics.csv')
strict = read(TABLE/'strict_37_ledger.csv')
admission = read(TABLE/'admission_decision_ledger.csv')
surveys = read(TABLE/'dietary_strata.csv')
subsets = read(TABLE/'robustness_subsets.csv')
rank_rows = read(OUT/'diagnostics/interval_rank_bounds.csv')
rank_by_unit = {r['unit']:r for r in rank_rows}
disclosure = js(ROOT/'00_admin/local_data_readiness_20260930/disclosure_audit.json')
brazil = js(ROOT/'00_admin/local_data_readiness_20260930/brazil_two_pair_feasibility.json')
assert (len(cells),len(strict),len(admission),len(surveys)) == (19,37,262,88)
for source in list(disclosure['sources'].values()) + brazil['sources']:
    p = Path(source['file'])
    assert p.is_relative_to(Path(P['raw_data_root'])) and sha(p) == source['sha256']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
    'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,'axes.spines.top':False,
    'axes.spines.right':False,'axes.linewidth':.65,'legend.frameon':False,'legend.fontsize':7,
    'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'govh-panel-v9','savefig.dpi':300})
BLUE, INK, GREY, ORANGE = '#0072B2','#30343B','#B6BDC4','#D55E00'
registry = []
def panel(ax, letter, name):
    ax.set_gid('panel_'+letter)
    ax.set_title(letter+'  '+name, loc='left', fontweight='bold', pad=11)
def save(fig, stem, panels, caption):
    files=[]
    for ext in ['svg','pdf','png']:
        p=FIG/(stem+'.'+ext)
        fig.savefig(p, facecolor='white', bbox_inches='tight', metadata={'Creator':'Reproducible matplotlib figure'})
        if ext=='svg':
            t=p.read_text();assert '<text' in t and '<image' not in t
            assert all('id="panel_'+x+'"' in t for x in panels)
        files.append({'path':str(p.relative_to(OUT)),'sha256':sha(p)})
    registry.append({'stem':stem,'panels':list(panels),'caption':caption,'files':files})
    plt.close(fig)

# Figure 1: three distinct questions; no unsupported source-to-admission attrition rate.
fig=plt.figure(figsize=(7.2,5.7))
gs=fig.add_gridspec(2,2,height_ratios=[1,1.15],hspace=.68,wspace=.95)
a,b,c=fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,:])
panel(a,'A','Admission audit (262 units)')
v=[19,199,44];labels=['Admitted','Held','Below support rule']
a.barh(range(3),v,color=[BLUE,GREY,GREY],height=.48)
a.set_yticks(range(3),labels);a.invert_yaxis();a.set(xlim=(0,225),xlabel='Candidate units')
for i,n in enumerate(v):a.text(n+3,i,str(n),va='center',fontsize=8)
panel(b,'B','Residue definition (37 units)')
v=[18,1,10,8];labels=['Exact match','Expression conversion','Mismatch; no conversion','Unresolved']
b.barh(range(4),v,color=[BLUE,BLUE,GREY,GREY],height=.5)
b.set_yticks(range(4),labels);b.invert_yaxis();b.set(xlim=(0,21),xlabel='Strict MACP units')
for i,n in enumerate(v):b.text(n+.3,i,str(n),va='center',fontsize=8)
panel(c,'C','Sample support within the 37-unit set')
for admitted, label, col, marker in [(False,'Held',GREY,'s'),(True,'Admitted',BLUE,'o')]:
    rs=[r for r in strict if (r['residue_definition_status'] in ['RD_EXACT','RD_CONVERSION_AVAILABLE'])==admitted]
    # Bubble area preserves multiplicity; coordinates are not jittered.
    points=Counter((int(r['sample_n']),100*int(r['quantified_n'])/int(r['sample_n'])) for r in rs)
    c.scatter([x[0] for x in points],[x[1] for x in points],s=[25*n for n in points.values()],c=col,marker=marker,label=label,edgecolors='white',linewidths=.4)
c.set(xlabel='Tested samples per unit',ylabel='Quantified results (%)',xlim=(0,230),ylim=(0,48))
c.legend(loc='upper right',ncol=2)
save(fig,'figure_1_qualification','ABC',
    'Qualification of monitoring units. (A) Recorded dispositions of 262 admission candidates. (B) Residue-definition decisions in the 37-unit strict MACP subset: 18 exact matches, one documented expression conversion and 18 held units. (C) Sample count and quantified fraction in that subset; marker area is proportional to the number of units at identical coordinates within each disposition. Coordinates are not jittered. The admitted set is selected by study-specific rules, not an estimate of general readiness prevalence. The separate 305,320-record temporal diagnostic is not the denominator of this admission audit.')

ds=sorted(cells,key=lambda r:float(r['max_mean_percent_ADI_UB']),reverse=True)
y=np.arange(len(ds));labels=[r['occurrence_country']+'  '+r['pesticide'] for r in ds]
fig=plt.figure(figsize=(7.2,8.0))
gs=fig.add_gridspec(2,2,height_ratios=[2.5,1],width_ratios=[1.65,1],hspace=.47,wspace=.18)
a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1],sharey=a);c=fig.add_subplot(gs[1,:])
panel(a,'A','Single-food contributions');panel(b,'B','Ordering under censoring')
for i,r in enumerate(ds):a.plot([float(r['max_mean_percent_ADI_LB']),float(r['max_mean_percent_ADI_UB'])],[i,i],color=BLUE,lw=1.3)
a.scatter([float(r['max_mean_percent_ADI_UB']) for r in ds],y,c=BLUE,s=14,label='Survey-mean UB')
a.scatter([float(r['max_native_HRP_percent_ADI_UB']) for r in ds],y,facecolors='white',edgecolors=INK,s=22,marker='D',label='Native high-percentile UB')
a.set_yticks(y,labels);a.set_ylim(18.8,-.8);a.set_xscale('log');a.set_xlabel('ADI (%) · logarithmic scale')
a.set_xticks([.0001,.001,.01,.1,1,10],['0.0001','0.001','0.01','0.1','1','10'])
fig.legend(*a.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.60,1.015),ncol=2,fontsize=7)
for i,r in enumerate(ds):
    rr=rank_by_unit[r['occurrence_country']+' '+r['pesticide']]
    low,high=int(rr['earliest_rank_outer_bound']),int(rr['latest_rank_outer_bound'])
    assert low<=i+1<=high
    b.plot([low,high],[i,i],color=GREY,lw=2)
b.scatter(range(1,20),y,c=INK,s=12)
b.set(xlim=(.4,19.6),xlabel='Rank (1 = largest contribution)');b.tick_params(axis='y',left=False,labelleft=False)
b.set_xticks([1,5,10,15,19]);b.spines['left'].set_visible(False)
for ax in [a,b]:ax.grid(axis='x',color='#E4E7EA',lw=.5);ax.set_axisbelow(True)
panel(c,'C','Dietary-survey age at the 2022 occurrence snapshot')
gaps=Counter(int(float(r['survey_gap_to_monitoring_years'])) for r in surveys)
c.bar(sorted(gaps),[gaps[k] for k in sorted(gaps)],width=.7,color=BLUE)
c.set(xlabel='2022 − dietary survey end year',ylabel='Dietary strata',xticks=range(10,23,2))
c.yaxis.set_major_locator(MaxNLocator(integer=True));c.set_ylim(0,max(gaps.values())+3)
for x,n in sorted(gaps.items()):c.text(x,n+.25,str(n),ha='center',fontsize=7)
fig.subplots_adjust(left=.26,right=.99,top=.93,bottom=.08)
save(fig,'figure_2_primo','ABC',
    'Saved PRIMo results, ordering uncertainty and dietary-survey age. (A) Each row is an admitted market–chemical unit. Blue segments join separately maximised lower- and upper-bound survey-mean contributions; filled circles mark upper means and open diamonds mark the largest native high-percentile upper contribution. Maxima for different endpoints need not arise in the same dietary stratum; native percentiles are not uniformly P95. (B) Grey segments show conservative rank bounds implied by the lower/upper mean intervals; black points show the ordering by upper means. Overlap does not establish jointly achievable rank reversals. These are ranks of displayed single-food %ADI contributions, not disease risk or intervention priorities. Neither panel represents confidence intervals. (C) Gap between the 2022 occurrence year and survey end year, counting each of 88 dietary strata once. Strata share surveys. CZ and DE denote occurrence markets, not production origin or population represented. Single-food contributions do not establish total-diet safety.')

cf,tf=disclosure['sources']['CFIA_2009_2010'],disclosure['sources']['TFDA_retail']
dist={int(re.match(r'\d+',k)[0]):v for k,v in cf['screen_results'].items()}
assert sum(dist.values())==3078 and sum(k*v for k,v in dist.items())==2200
fig=plt.figure(figsize=(7.2,6.3))
gs=fig.add_gridspec(2,2,height_ratios=[1.2,1],hspace=.88,wspace=.6)
a,b,c=fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,:])
panel(a,'A','CFIA: screening summaries')
a.bar(range(12),[dist.get(i,0) for i in range(12)],color=BLUE,width=.75)
a.set(xlabel='Declared detections per summary',ylabel='Summaries',xticks=range(0,12,2),ylim=(0,2050))
for x,n in sorted(dist.items()):a.text(x,n+26,str(n),ha='center',fontsize=6.5)
panel(b,'B','TFDA: published result strings')
vals=[tf['result_text_counts']['合格'],tf['rows']-tf['result_text_counts']['合格']]
b.bar([0,1],vals,width=.5,color=[GREY,BLUE]);b.set_xticks([0,1],['Compliance\nlabel only','Other result\nstrings'])
b.set(ylabel='Rows (not unique samples)',ylim=(0,28000));b.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
for x,n in enumerate(vals):b.text(x,n+550,f'{n:,}',ha='center',fontsize=8)
panel(c,'C','PARA: tomato denominators reconciled across documents')
parts=[]
for key in ['Acefato','Acetamiprido']:
    r=brazil['pairs'][key];classes=r['reporting_classes']
    parts.append([classes.get('NUMERIC_REPORTED',0),classes.get('DETECTED_BELOW_QUANTIFICATION',0),r['samples_without_listed_target_result']])
bottom=np.zeros(2)
for j,(label,col,hatch) in enumerate([('Numeric detection',BLUE,None),('Detected below LOQ',ORANGE,'///'),('Aggregate non-detection',GREY,None)]):
    vals=[x[j] for x in parts]
    c.barh([0,1],vals,left=bottom,color=col,hatch=hatch,height=.42,label=label,edgecolor='white',linewidth=.5)
    for i,n in enumerate(vals):
        if n:
            if n<20:c.annotate(str(n),(bottom[i]+n/2,i),xytext=(0,-19),textcoords='offset points',ha='center',fontsize=7,arrowprops={'arrowstyle':'-','lw':.6})
            else:c.text(bottom[i]+n/2,i,str(n),ha='center',va='center',fontsize=8,color='white' if j==0 else INK)
    bottom+=vals
assert list(bottom)==[316,316]
c.set_yticks([0,1],['Acephate','Acetamiprid']);c.set(xlim=(0,330),xlabel='Tested samples per analyte',ylim=(1.65,-.6))
c.legend(loc='upper center',bbox_to_anchor=(.5,-.32),ncol=3,fontsize=7)
fig.subplots_adjust(left=.13,right=.98,top=.93,bottom=.19)
save(fig,'figure_3_disclosure','ABC',
    'Different disclosure structures permit different denominator checks. (A) CFIA 2009–2010: 3,078 screening summaries reconcile with 2,200 component-result rows. A declared zero detection does not disclose a chemical-specific tested panel or numerical limit. (B) TFDA saved retail export: literal compliance labels and other result strings, with repeated rows retained; the latter category is not a count of unique noncompliant samples. (C) Brazilian PARA 2017–2018: each selected analyte was tested in 316 tomato samples. Companion documents distinguish numeric detections, detected-below-LOQ results and aggregate non-detections. Non-detections are reconciled counts, not measured zeros or an imputed negative matrix. The panels use different record units and are not a comparison of national exposure, contamination prevalence or programme performance. Cases were purposively selected after inspection; no exposure unit was added.')

fig,(a,b)=plt.subplots(1,2,figsize=(7.2,3.4),gridspec_kw={'width_ratios':[1,1.25]})
labels=['Exact definition only','Exact + converted (primary)','Tested samples ≥50','Quantified fraction ≥10%','Survey end year ≥2010']
y=np.arange(5)
panel(a,'A','Retained occurrence units');panel(b,'B','Largest survey-mean UB')
a.scatter([int(r['cells']) for r in subsets],y,c=BLUE,s=24)
for i,r in enumerate(subsets):a.annotate(r['cells'],(int(r['cells']),i),xytext=(5,0),textcoords='offset points',va='center',fontsize=7)
b.scatter([float(r['max_mean_percent_ADI_UB']) for r in subsets],y,c=BLUE,s=24)
for i,r in enumerate(subsets):b.annotate(f"{float(r['max_mean_percent_ADI_UB']):.4f}",(float(r['max_mean_percent_ADI_UB']),i),xytext=(5,0),textcoords='offset points',va='center',fontsize=7)
a.set_yticks(y,labels);b.set_yticks(y,[])
a.set(xlim=(0,23),xlabel='Occurrence units');b.set(xlim=(0,4.8),xlabel='ADI (%)')
for ax in [a,b]:ax.set_ylim(4.6,-.6);ax.grid(axis='x',lw=.5,color='#E4E7EA');ax.set_axisbelow(True)
fig.subplots_adjust(left=.31,right=.98,wspace=.3,bottom=.2,top=.86)
save(fig,'figure_S1_subsets','AB',
    'Composition-sensitive restrictions of the saved analysis. (A) Retained occurrence-unit counts. (B) Largest upper-bound survey-mean contribution among retained scenarios. The survey-year restriction changes dietary profiles but retains 19 occurrence units. Results do not estimate risk reduction, temporal change or an intervention effect; the full recorded subsets are in tables/robustness_subsets.csv.')

assert all(sha(ROOT/x['path'])==x['sha256'] for x in inputs)
(OUT/'figure_registry.json').write_text(json.dumps({'freeze_files_verified':len(freeze['files']),'inputs':inputs,'figures':registry,'new_exposure_calculations':0},indent=2)+'\n')
print(json.dumps({'figures':len(registry),'panels':sum(len(x['panels']) for x in registry),'freeze_verified':len(freeze['files'])}))
