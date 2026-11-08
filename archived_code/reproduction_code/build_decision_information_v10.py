"""Editable information-scenario and real nondetect-case panels; no image assets."""
import csv, hashlib, json, shutil
from pathlib import Path
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
P=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=ROOT/'08_manuscript/decision_revision_v10'; FIG=OUT/'figures'; FIG.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((ROOT/'08_manuscript/panel_revision_v9/figure_registry.json').read_text())
for item in old['figures']:
    for f in item['files']:
        src=ROOT/'08_manuscript/panel_revision_v9'/f['path']; dest=FIG/src.name
        assert sha(src)==f['sha256']
        if dest.exists(): assert sha(dest)==sha(src)
        else: shutil.copy2(src,dest)
with (OUT/'tables/information_scenario_summary.csv').open() as f:r=list(csv.DictReader(f))
with (OUT/'tables/all_nondetect_examples.csv').open() as f:nd=list(csv.DictReader(f))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
    'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'axes.spines.top':False,
    'axes.spines.right':False,'axes.linewidth':.65,'legend.frameon':False,'legend.fontsize':7,
    'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'govh-decision-v10'})
fig,(a,b)=plt.subplots(2,1,figsize=(7.2,6.1),gridspec_kw={'height_ratios':[1.6,1],'hspace':.72})
a.set_gid('panel_A'); b.set_gid('panel_B')
a.set_title('A  Hypothetical information from lower reporting limits',loc='left',weight='bold',pad=12)
for name,label,col,style in [('ZERO','All below new limits (theta = 0 or 0.05)','#0072B2','-'),
    ('MID_025','theta = 0.25','#D55E00','--'),('HIGH_075','theta = 0.75','#757575',':'),
    ('HETEROGENEOUS','Mixed theta = 0.05 / 0.25 / 0.75','#009E73','-.')]:
    rows=[x for x in r if x['allocation']==name]
    a.plot([1-float(x['limit_ratio_r']) for x in rows],[int(x['unresolved_pairs']) for x in rows],style,
        color=col,marker='o',ms=3,lw=1.3,label=label)
a.set(xlabel='New / original reporting limit',ylabel='Unresolved pairs (of 171)',
    xticks=[0,.5,.8,.9],xticklabels=['1.0','0.5','0.2','0.1'],ylim=(-3,85),xlim=(-.02,.92))
a.annotate('Observed baseline: 79',(0,79),xytext=(7,-16),textcoords='offset points',fontsize=7)
a.grid(axis='y',color='#E4E7EA',lw=.5);a.set_axisbelow(True)
a.legend(loc='upper right',bbox_to_anchor=(1,1),fontsize=7)
b.set_title('B  All-nondetect records still bound monitored concentrations',loc='left',weight='bold',pad=12)
for i,row in enumerate(nd):
    u=float(row['monitored_mean_upper_mg_kg'])
    b.plot([0,u],[i,i],color='#0072B2',lw=2)
    b.scatter([0,u],[i,i],c='#0072B2',s=18)
    b.text(u+.00015,i,f'{u:.6f}',va='center',fontsize=8)
b.set(yticks=[0,1],yticklabels=['Cyazofamid','Mandipropamid'],ylim=(1.65,-.65),xlim=(-.00015,.0101),
    xlabel='Monitored-expression mean interval (mg/kg)',xticks=[0,.002,.004,.006,.008,.01])
b.text(.5,.95,'2022 DE MACP tomato: 214 samples; 0 quantified, per chemical',transform=b.transAxes,ha='center',fontsize=7)
b.grid(axis='x',color='#E4E7EA',lw=.5);b.set_axisbelow(True)
fig.subplots_adjust(left=.18,right=.98,top=.94,bottom=.1)
caption=('Information scenarios and complete all-nondetect examples. (A) Deterministic ideal remeasurement scenarios for the existing 19 units. theta is the assumed fraction of each historical reporting limit occupied by its unknown censored concentration; it is not estimated from data. The mixed allocation cycles 0.05/0.25/0.75 over alphabetically ordered unit identifiers. Quantified values are fixed; above the new limit measurement is assumed exact. Curves count interval-separated comparisons on the saved displayed mean-%ADI scale, not risk rankings or predicted laboratory performance. At the original limits all scenarios reproduce the observed 79 unresolved pairs of 171. (B) Recomputed monitored-expression concentration bounds for two complete all-nondetect German raw-tomato strata. Each has 214 sample records with heterogeneous reporting limits. The chemical rows are not independent sample populations. Bounds are not confidence intervals, absence declarations or new PRIMo estimates. Documentary mandipropamid fruit-crop compatibility does not certify full laboratory expression coverage or exposure admission; cyazofamid target-specific risk compatibility remains unadjudicated.')
files=[]
for ext in ['svg','pdf','png']:
    path=FIG/('figure_4_information.'+ext)
    fig.savefig(path,bbox_inches='tight',dpi=300,facecolor='white')
    if ext=='svg':
        text=path.read_text();assert '<image' not in text and '<text' in text
        assert all('id="panel_'+x+'"' in text for x in 'AB')
    files.append({'path':str(path.relative_to(OUT)),'sha256':sha(path)})
plt.close(fig)
registry={'freeze_files_verified':old['freeze_files_verified'],'figures':old['figures']+[{'stem':'figure_4_information','panels':['A','B'],'caption':caption,'files':files}],
    'information_scenarios':'Hypothetical analytical refinement; no new native PRIMo result',
    'new_empirical_exposure_units':0}
(OUT/'figure_registry.json').write_text(json.dumps(registry,indent=2)+'\n')
print(json.dumps({'figures':5,'panels':13,'native_runs':0}))
