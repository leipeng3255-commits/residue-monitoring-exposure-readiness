"""Rebuild two supplement figures from frozen, project-local source tables.

No new exposure or primary result is calculated. The external project path is
read from paths.yaml; original sources are never modified.
"""
from pathlib import Path
import csv, json, hashlib, re, argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib import gridspec
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
config={}
for line in (ROOT/'00_admin/paths.yaml').read_text().splitlines():
 m=re.match(r'^([a-z_]+):\s*"(.*)"\s*$',line)
 if m: config[m.group(1)]=m.group(2)
assert Path(config['project_root']).resolve()==ROOT
parser=argparse.ArgumentParser(description='Replot S4/S5 from five authorised saved source tables')
parser.add_argument('--input-dir',required=True,type=Path,help='Directory containing the five saved, authorised source tables')
parser.add_argument('--out',required=True,type=Path,help='New output directory; existing directories are never replaced')
args=parser.parse_args()
src=args.input_dir.resolve()
O=args.out.resolve()
if O.exists(): raise FileExistsError(f'Refusing to overwrite output directory: {O}')
O.mkdir(parents=True)
inputs=[src/name for name in ['figure_field_availability.csv','panel_b_structure_scale.csv','panel_c_california_annual_structure.csv','panel_d_arithmetic_reproducibility.csv','tomato_reporting_summary.csv']]
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
fields,structures,cal,arith,annual=map(read,inputs)
assert len(fields)==10 and sum(r['evidence_level']=='C' for r in fields)==5 and sum(r['evidence_level']=='D' for r in fields)==5
assert sum(int(r['count']) for r in structures if r['source']=='WHO GEMS/Food')==8168962
assert sum(int(r['reported_crop_analyte_rows']) for r in annual)==254
lookup={(r['audit'],r['category']):int(r['count']) for r in arith}
assert [r['count'] for r in arith]==['120','130','147','7','4','23','2']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.3,'axes.labelsize':9.3,'xtick.labelsize':9.3,'ytick.labelsize':9.3,'legend.fontsize':9.3,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7})
blue='#156E99'; orange='#C37318'; green='#297D68'; gray='#999FA3'; purple='#8A78A6'; pale='#E6E8EA'; salmon='#D28C7F'
states=['NO','SCHEMA_ONLY','PARTIAL_AGGREGATE','AGGREGATE_ONLY','REPORT_INTERNAL_ONLY','PARTIAL_ROW_LEVEL','ROW_LEVEL']
colors=[pale,purple,'#E9BC69','#80AAC8','#8EC6B4',salmon,green]
hatches=['','..','//','\\\\','xx','++','--']
names=['Not reported','Schema only','Partial aggregate','Aggregate only','Report-internal','Partial rows','Row-level']
columns=['sample_id','commodity','pesticide_analyte','quantitative_concentration','non_detect_information','lod_loq','risk_assessment_residue_definition','sampling_year','food_form','country_market_frame','organic_conventional_status','compatible_dietary_linkage']
labels=['Sample ID','Commodity','Analyte','Concentration','Non-detect','LOD/LOQ','Risk definition','Year','Food form','Market/origin','Organic label','Dietary link']
short=['Thailand FDA [D]','Thailand ACFS [D]','THRASFF alerts [D]','THRASFF guide [D]','Israel audit [D]','Israel MoH [C]','Belgium FASFC [C]','Israel Agriculture [C]','WHO GEMS/Food [C]','California DPR [C]']

def letter(ax,s):ax.text(-.14,1.02,s,transform=ax.transAxes,fontweight='bold',fontsize=13,ha='left',va='bottom')
def save(fig,stem):
 fig.savefig(O/(stem+'.svg'),format='svg',metadata={'Date':'2026-11-09','Creator':'Matplotlib; AI-assisted code'})
 fig.savefig(O/(stem+'.pdf'),format='pdf',metadata={'Creator':'Matplotlib; AI-assisted code'})
 fig.savefig(O/(stem+'.png'),format='png',dpi=300)
 fig.savefig(O/(stem+'.tiff'),format='tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
 plt.close(fig)

fig=plt.figure(figsize=(7.0866,10.0));gs=gridspec.GridSpec(4,2,figure=fig,height_ratios=[3.1,.45,1.65,1.65],hspace=.72,wspace=.5)
ax=fig.add_subplot(gs[0,:]);letter(ax,'A')
for y,row in enumerate(fields):
 for x,col in enumerate(columns):
  idx=states.index(row[col]);ax.add_patch(Rectangle((x,y),1,1,facecolor=colors[idx],edgecolor='white',linewidth=.45,hatch=hatches[idx]))
ax.set_xlim(0,12);ax.set_ylim(10,0);ax.set_xticks(np.arange(12)+.5,labels,rotation=43,ha='right');ax.set_yticks(np.arange(10)+.5,short);ax.tick_params(length=0);[s.set_visible(False) for s in ax.spines.values()]
ax.set_title('Source-specific field evidence',loc='left',fontsize=10,pad=6)
legax=fig.add_subplot(gs[1,:]);legax.axis('off');legax.legend(handles=[Patch(facecolor=colors[i],edgecolor='#555',hatch=hatches[i],label=names[i],linewidth=.3) for i in range(7)],ncol=4,loc='center',frameon=False,columnspacing=.45,handlelength=1.0,fontsize=9.3)

ax=fig.add_subplot(gs[2,0]);letter(ax,'B');who=[x for x in structures if x['source']=='WHO GEMS/Food']; y=np.arange(len(who));v=[int(x['count'])/1e6 for x in who];bars=ax.barh(y,v,color=[green,gray,'#CACED0'],edgecolor='#333',hatch=['','//','..']);ax.set_yticks(y,[x['structure'].replace(' record type','') for x in who]);ax.invert_yaxis();ax.set_xlabel('Analytical rows (millions)');ax.set_title('WHO GEMS/Food',loc='left',fontsize=10);ax.set_xlim(0,max(v)*1.26)
for b,x in zip(bars,who):
 inside=b.get_width()>2
 ax.text(b.get_width()-.06 if inside else b.get_width()+.04,b.get_y()+b.get_height()/2,f"{int(x['count']):,}",ha='right' if inside else 'left',color='white' if inside else 'black',va='center',fontsize=9.3)
ax=fig.add_subplot(gs[2,1]);letter(ax,'C'); x=np.arange(len(cal));width=.24
for off,key,label,color,hatch in [(-width,'unique_lab_ids','Lab IDs',gray,'..'),(0,'detected_analyte_rows','Detected rows',blue,''),(width,'generic_nd_placeholder_rows','Generic ND',orange,'//')]:
 ax.bar(x+off,[int(z[key]) for z in cal],width,label=label,color=color,hatch=hatch,edgecolor='#333',linewidth=.3)
ax.set_xticks(x,[z['year'] for z in cal]);ax.set_ylabel('Year-specific records');ax.set_title('California DPR',loc='left',fontsize=10);ax.legend(frameon=False,fontsize=9.3,loc='upper left');ax.set_ylim(0,10000)
ax=fig.add_subplot(gs[3,:]);ax.text(-.09,1.15,'D',transform=ax.transAxes,fontweight='bold',fontsize=13,ha='left',va='bottom'); y=[int(r['reported_crop_analyte_rows']) for r in annual];x=np.arange(len(annual));bars=ax.bar(x,y,color=blue,edgecolor='#333',hatch='//');ax.set_xticks(x,[r['year'] for r in annual]);ax.set_ylabel('Published crop–analyte rows');ax.set_xlabel('Reporting year');ax.set_ylim(0,58);ax.set_title('Israel Agriculture: tomato tables (seven reports)',loc='left',fontsize=10)
for b,v in zip(bars,y):ax.text(b.get_x()+b.get_width()/2,v+1,str(v),ha='center',fontsize=9.3)
fig.subplots_adjust(left=.27,right=.98,top=.94,bottom=.07)
save(fig,'C02_Figure_S4_Final')

fig,axs=plt.subplots(1,3,figsize=(7.0866,3.05),gridspec_kw={'wspace':.53});
ax=axs[0];letter(ax,'A');acfs=[lookup[('ACFS FY2020 printed safe count',k)] for k in ['Printed','Arithmetic reconstruction']];bars=ax.bar([0,1],acfs,color=[orange,green],edgecolor='#333',hatch=['//','..']);ax.set_xticks([0,1],['Printed','Rebuilt']);ax.set_ylabel('Safe-count value');ax.set_ylim(0,160)
for b,v in zip(bars,acfs):ax.text(b.get_x()+b.get_width()/2,v+3,str(v),ha='center',fontsize=9.3)
ax.set_title('ACFS FY2020',loc='left',fontsize=9.3)
ax=axs[1];letter(ax,'B');v=[lookup[('Israel tomato mean-bound rows',k)] for k in ['Feasible','Inconsistent','Incomplete']];bars=ax.bar([0,1,2],v,color=[green,orange,gray],edgecolor='#333',hatch=['','//','..']);ax.set_xticks([0,1,2],['Feasible','Inconsist.','Incomplete'],rotation=28,ha='right');ax.set_ylabel('Crop–analyte rows');ax.set_ylim(0,180);ax.set_title('Israel tomato tables',loc='left',fontsize=9.3)
for b,n in zip(bars,v):ax.text(b.get_x()+b.get_width()/2,n+3,str(n),ha='center',fontsize=9.3)
ax=axs[2];letter(ax,'C');identities=[lookup[('Israel annual identities',k)] for k in ['Reproduced','Inconsistent']];bars=ax.bar([0,1],identities,color=[green,orange],edgecolor='#333',hatch=['','//']);ax.set_xticks([0,1],['Reproduced','Inconsist.'],rotation=28,ha='right');ax.set_ylim(0,29);ax.set_ylabel('Printed identities');ax.set_title('Israel annual reports',loc='left',fontsize=9.3)
for b,n in zip(bars,identities):ax.text(b.get_x()+b.get_width()/2,n+.6,str(n),ha='center',fontsize=9.3)
fig.subplots_adjust(left=.08,right=.99,top=.87,bottom=.3)
save(fig,'C05_Figure_S5_Final')

receipts=[]
for x in inputs:receipts.append({'input_file':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()})
(O/'figure_source_receipts.json').write_text(json.dumps({'input_files':receipts,'source_count':10,'levels':{'C':5,'D':5},'who_rows':8168962,'israel_tomato_rows':254,'acfs':[120,130],'israel_rows':[147,7,4],'israel_identities':[23,2],'figure_width_mm':180,'minimum_font_pt':9.3,'new_exposure_calculations':0},indent=2))
print('S4 and S5 created from frozen source tables; no new exposure results')
