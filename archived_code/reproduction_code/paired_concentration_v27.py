"""Portable aggregate-only replay; no exposure calculation or manual editing."""
import argparse,csv,hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args()
import yaml
config=yaml.safe_load((args.data.parent/'paths.yaml').read_text())
assert config['mode']=='saved_derived_replay_only'
args.out.mkdir(parents=True,exist_ok=False)
def read(n):
    with (args.data/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
rows=read('paired_concentration_bounds.csv');balance=read('shared_sample_metadata_balance.csv')
assert len(rows)==15 and len({r['active_code'] for r in rows})==15
assert all(r['direction']=='DIRECTION_UNRESOLVED' and float(r['difference_LB_mg_kg'])<0<float(r['difference_UB_mg_kg']) for r in rows)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':9,'axes.labelsize':9,
 'xtick.labelsize':8,'ytick.labelsize':8.5,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
 'axes.linewidth':.6,'savefig.facecolor':'white'})
fig=plt.figure(figsize=(7.2,7.6));gs=fig.add_gridspec(2,2,height_ratios=[4.7,1.0],left=.23,right=.98,bottom=.19,top=.88,wspace=.22,hspace=.58)
a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1],sharey=a);c=fig.add_subplot(gs[1,:])
blue='#0072B2';orange='#D55E00';grey='#4D4D4D'
for i,r in enumerate(rows):
    for group,offset,col,marker in [('organic',-.14,blue,'o'),('nonorganic',.14,orange,'s')]:
        l=float(r[group+'_LB_mg_kg'])*1000;u=float(r[group+'_UB_mg_kg'])*1000
        a.plot([l,u],[i+offset]*2,c=col,lw=1.7,solid_capstyle='butt')
        a.plot([l,u],[i+offset]*2,linestyle='none',marker=marker,markersize=3.4,c=col,markerfacecolor='white',markeredgewidth=.9)
    dl=float(r['difference_LB_mg_kg'])*1000;du=float(r['difference_UB_mg_kg'])*1000
    b.plot([dl,du],[i]*2,c=grey,lw=1.8)
    b.plot([dl,du],[i]*2,linestyle='none',marker='|',markersize=5,c=grey)
a.set_yticks(range(15),[r['pesticide'].capitalize() for r in rows]);a.set_ylim(14.6,-.7)
a.set_xlim(-.5,16);a.set_xticks([0,5,10,15]);a.set_xlabel('Sampled mean concentration (µg/kg)')
b.tick_params(axis='y',left=False,labelleft=False);b.spines['left'].set_visible(False)
b.set_xlim(-16,13);b.set_xticks([-15,-10,-5,0,5,10]);b.axvline(0,c='#555555',ls='--',lw=.8,zorder=0)
b.set_xlabel('Organic − nonorganic (µg/kg)')
for ax in [a,b]:ax.grid(axis='x',color='#DADADA',lw=.4);ax.set_axisbelow(True)
a.set_title('A  Concentration bounds',loc='left',fontweight='bold',fontsize=10,pad=12)
b.set_title('B  Difference bounds',loc='left',fontweight='bold',fontsize=10,pad=12)
top_legend=fig.legend(handles=[Line2D([0],[0],c=blue,marker='o',mfc='white',lw=1.7,label='Source-declared organic'),
    Line2D([0],[0],c=orange,marker='s',mfc='white',lw=1.7,label='Source-declared nonorganic')],
    loc='upper center',bbox_to_anchor=(.60,.982),ncol=2,frameon=False,fontsize=8.5,columnspacing=1.4,handlelength=1.5)
groups=[('A07SE','Organic (n = 28)'),('A0C6Y','Nonorganic (n = 186)')]
categories=[('ES','Spain','#0072B2',''),('DE','Germany','#E69F00','//'),('NL','Netherlands','#009E73','..'),('other','Other/unknown','#999999','xx')]
for j,(prod,label) in enumerate(groups):
    observed={r['value']:int(r['distinct_samples']) for r in balance if r['field']=='origCountry' and r['production_code']==prod}
    total=sum(observed.values());assert total in [28,186];left=0
    for code,cat,col,hatch in categories:
        n=observed.get(code,0) if code!='other' else sum(n for k,n in observed.items() if k not in ['ES','DE','NL'])
        width=100*n/total;c.barh(j,width,left=left,color=col,edgecolor='white',lw=.7,hatch=hatch,height=.50,label=cat if j==0 else None)
        if width>=8:c.text(left+width/2,j,str(n),ha='center',va='center',fontsize=8.5,color='white' if code in ['ES','NL'] else '#222222')
        left+=width
c.set_yticks([0,1],[x[1] for x in groups]);c.set_ylim(1.6,-.65);c.set_xlim(0,100);c.set_xticks([0,25,50,75,100])
c.set_xlabel('Production origin within each sampled group (%)');c.spines['left'].set_visible(False);c.tick_params(axis='y',length=0)
c.set_title('C  Different origin composition; not a causal comparison',loc='left',fontweight='bold',fontsize=10,pad=12)
bottom_legend=c.legend(loc='lower center',bbox_to_anchor=(.50,-1.0),ncol=4,frameon=False,fontsize=8.5,handlelength=1.4,columnspacing=1.5)
footnote=fig.text(.23,.028,'Germany, 2022 MACP tomato RPC • Censoring bounds, not confidence intervals',fontsize=8.3,color='#444444')
fig.canvas.draw();renderer=fig.canvas.get_renderer()
assert not top_legend.get_window_extent(renderer).overlaps(a._left_title.get_window_extent(renderer))
assert not top_legend.get_window_extent(renderer).overlaps(b._left_title.get_window_extent(renderer))
assert not bottom_legend.get_window_extent(renderer).overlaps(footnote.get_window_extent(renderer))
stem='figure_S2_organic_identification'
for ext in ['svg','pdf','png']:fig.savefig(args.out/(stem+'.'+ext),dpi=600)
with Image.open(args.out/(stem+'.png')) as im:im.save(args.out/(stem+'.tiff'),compression='tiff_lzw',dpi=(600,600))
plt.close(fig)
assert '<image' not in (args.out/(stem+'.svg')).read_text() and '<text' in (args.out/(stem+'.svg')).read_text()
receipt={'panels':['S2A','S2B','S2C'],'chemical_comparisons':15,'distinct_lots':214,'shared_analyte_sample_denominators_not_summed':True,
 'all15_difference_intervals_contain_zero':True,'new_exposure':False,'svg_editable_text_and_vectors':True,
 'input_hashes':{n:hashlib.sha256((args.data/n).read_bytes()).hexdigest() for n in ['paired_concentration_bounds.csv','shared_sample_metadata_balance.csv']},
 'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.iterdir() if p.is_file()}}
(args.out/'figure_validation.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({'panels':3,'data_rows':15,'editable_svg':True}))

