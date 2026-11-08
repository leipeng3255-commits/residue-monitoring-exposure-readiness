"""Eight question-linked quantitative panels; editable SVG, no invented observations."""
import argparse,collections,csv,hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter,MaxNLocator
import numpy as np
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert not a.out.exists();a.out.mkdir(parents=True)
    def read(n):return list(csv.DictReader((a.data/n).open()))
    cols=read('eat2_whole_and_vegetable_denominators.csv');coverage=read('eat2_group_chemical_coverage.csv');thresholds=read('eati_censor_threshold_distribution.csv');examples=read('eati_source_interval_examples.csv');nz=read('nz_difference_endpoint_counts.csv')
    rec=json.loads((a.data/'reassessment_summary.json').read_text());brazil=json.loads((a.data/'brazil_two_pair_feasibility.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':7,'axes.labelsize':7,'axes.titlesize':7,'xtick.labelsize':7,'ytick.labelsize':7,
       'legend.fontsize':7,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'tds-eight-v26','savefig.dpi':600})
    blue,green,orange,grey='#0072B2','#009E73','#D55E00','#88939D'
    fig=plt.figure(figsize=(7.2,6.65));gs=fig.add_gridspec(3,3,wspace=.68,hspace=1.25)
    axs=[fig.add_subplot(gs[0,:2]),fig.add_subplot(gs[0,2]),fig.add_subplot(gs[1,0]),fig.add_subplot(gs[1,1]),fig.add_subplot(gs[1,2]),fig.add_subplot(gs[2,0]),fig.add_subplot(gs[2,1]),fig.add_subplot(gs[2,2])]
    titles=['Coverage structure','Denominator sensitivity','Scope-specific factors','Quantification support','Reported censoring limits','Censoring envelopes','Recorded ordering','Recovered denominators']
    for i,(ax,t) in enumerate(zip(axs,titles)):
        letter=chr(65+i);ax.set_gid('panel_'+letter);ax.set_title(letter+'  '+t,loc='left',fontweight='bold',pad=8)
    order=sorted(range(1,323),key=lambda c:(float(cols[c-1]['whole_factor']),c))
    matrix=np.zeros((36,322))
    for r in coverage:matrix[int(r['group_rank'])-1,int(r['chemical_column'])-1]=float(r['tested_fraction'])
    m=axs[0].pcolormesh(matrix[:,np.array(order)-1],vmin=0,vmax=1,cmap='cividis',shading='nearest',rasterized=False)
    axs[0].invert_yaxis();axs[0].set(xlabel='Chemical columns (ordered by whole-food coverage)',ylabel='Source food-group rank',xticks=[0,160,321],xticklabels=['1','161','322'],yticks=[0,11,23,35],yticklabels=['1','12','24','36'])
    cb=fig.colorbar(m,ax=axs[0],fraction=.025,pad=.025);cb.solids.set_rasterized(False);cb.set_ticks([0,.5,1]);cb.set_ticklabels(['0%','50%','100%']);cb.ax.set_title('Tested',fontsize=7,pad=5)
    axs[0].text(0,-.54,'Rank 1: vegetables excluding potatoes; all 36 source groups retained',transform=axs[0].transAxes,fontsize=7)
    ax=axs[1]
    for data,color,label in [(sorted(float(r['whole_factor']) for r in cols),blue,'All foods (322)'),(sorted(float(r['vegetable_factor']) for r in cols if r['vegetable_factor']),green,'Vegetables (275)')]:
        ax.step(data,np.arange(1,len(data)+1)/len(data),where='post',color=color,lw=1,label=label)
    ax.set(xlim=(0,1.03),ylim=(0,1.03),xlabel='n_tested / n_all',ylabel='Cumulative share');ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_xticks([0,.5,1]);ax.set_yticks([0,.5,1]);ax.legend(loc='upper left',bbox_to_anchor=(0,-.48),handlelength=1,borderaxespad=0)
    ax=axs[2];valid=[r for r in cols if r['vegetable_factor']]
    counts=collections.Counter((float(r['whole_factor']),float(r['vegetable_factor'])) for r in valid)
    ax.scatter([x for x,y in counts],[y for x,y in counts],s=[5+2*np.sqrt(n) for n in counts.values()],c=blue,alpha=.75,linewidths=0)
    ax.plot([0,1],[0,1],color=grey,lw=.7,ls='--');ax.set(xlim=(-.03,1.03),ylim=(-.03,1.03),xlabel='All-food factor',ylabel='Vegetable factor',xticks=[0,.5,1],yticks=[0,.5,1]);ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    ax.text(0,-.57,'275 matched columns; 47 untested held',transform=ax.transAxes,fontsize=7)
    ax=axs[3];q=collections.Counter((int(r['vegetable_n_tested']),int(r['vegetable_n_VAL'])) for r in valid)
    ax.scatter([x for x,y in q],[y for x,y in q],s=[5+2*np.sqrt(n) for n in q.values()],c=green,alpha=.8,linewidths=0)
    ax.set(xlabel='Tested vegetable composites',ylabel='Quantified records',xlim=(0,280));ax.set_yscale('symlog',linthresh=1);ax.set_xticks([0,135,267]);ax.set_yticks([0,1,10,100]);ax.set_yticklabels(['0','1','10','100'])
    ax=axs[4]
    for st,color,label in [('<LD',blue,'<LOD: 63,350'),('<LQ',orange,'<LOQ: 583')]:
        rr=sorted([r for r in thresholds if r['type_res']==st],key=lambda r:float(r['upper_limit_ug_kg']));vals=np.array([float(r['upper_limit_ug_kg']) for r in rr]);ns=np.array([int(r['records']) for r in rr]);ax.step(vals,np.cumsum(ns)/sum(ns),where='post',color=color,lw=1,label=label)
    ax.set_xscale('log');ax.set(xlabel='Typed upper limit (µg/kg)',ylabel='Cumulative share',ylim=(0,1.03));ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_yticks([0,.5,1]);ax.legend(loc='upper left',bbox_to_anchor=(0,-.48),handlelength=1,borderaxespad=0)
    ax=axs[5];examples.sort(key=lambda r:({'<LD':0,'<LQ':1,'VAL':2}[r['type_res']],int(r['source_row'])))
    for i,r in enumerate(examples):
        l,u=float(r['lower_over_lq']),float(r['upper_over_lq']);color=blue if r['type_res']=='<LD' else orange if r['type_res']=='<LQ' else green
        if r['type_res']=='VAL':ax.plot(l,i,'o',ms=3,color=color)
        else:
            ax.plot([l,u],[i,i],color=color,lw=1);ax.plot([l,u],[i,i],'|',ms=4,color=color)
        # LOD is a reporting threshold, not a certified actual lower concentration.
        if r['type_res']=='<LQ':ax.plot(float(r['ld'])/float(r['lq']),i,'x',ms=3,color=grey)
    ax.set_yticks(range(6),[r['type_res']+' r'+r['source_row'] for r in examples]);ax.invert_yaxis();ax.set(xlabel='Envelope / record LOQ',ylabel='',xlim=(-.05,max(1.1,max(float(r['upper_over_lq']) for r in examples))*1.07));ax.xaxis.set_major_locator(MaxNLocator(3))
    ax=axs[6]
    for st,col,label in [('UNRESOLVED_CENSORING',grey,'Unresolved: 19,246'),('BRAND1_ABOVE',blue,'Above: 30'),('BRAND1_BELOW',orange,'Below: 31')]:
        rr=[r for r in nz if r['decision']==st];ax.scatter([float(r['difference_LB']) for r in rr],[float(r['difference_UB']) for r in rr],s=6,c=col,alpha=.7,linewidths=0,label=label)
    ax.set_xscale('symlog',linthresh=.001);ax.set_yscale('symlog',linthresh=.001);ax.axhline(0,color='black',lw=.5);ax.axvline(0,color='black',lw=.5)
    ax.set(xlabel='Lower endpoint (mg/kg)',ylabel='Upper endpoint (mg/kg)',xticks=[-1,0,1],yticks=[-1,0,1]);ax.set_xticklabels(['−1','0','1']);ax.set_yticklabels(['−1','0','1']);ax.legend(loc='upper left',bbox_to_anchor=(0,-.48),handlelength=.5,markerscale=.8,borderaxespad=0)
    ax=axs[7];parts=[]
    for k in ['Acefato','Acetamiprido']:
        r=brazil['pairs'][k];c=r['reporting_classes'];parts.append([c.get('NUMERIC_REPORTED',0),c.get('DETECTED_BELOW_QUANTIFICATION',0),r['samples_without_listed_target_result']])
    left=np.zeros(2)
    for j,col in enumerate([blue,orange,'#C1C7CD']):
        n=[r[j] for r in parts];ax.barh([0,1],n,left=left,color=col,height=.4,edgecolor='white',linewidth=.3,hatch='///' if j==1 else None)
        for i,v in enumerate(n):
            if v>=40:ax.text(left[i]+v/2,i,str(v),ha='center',va='center',fontsize=7,color='white' if j==0 else 'black')
            elif v and j==0:ax.annotate(str(v),(left[i]+v/2,i),xytext=(0,12),textcoords='offset points',ha='center',fontsize=7,arrowprops={'arrowstyle':'-','lw':.5})
            elif v:ax.annotate(str(v),(left[i]+v/2,i),xytext=(0,-13),textcoords='offset points',ha='center',fontsize=7,arrowprops={'arrowstyle':'-','lw':.5})
        left+=n
    assert list(left)==[316,316];ax.set_yticks([0,1],['Acephate','Acetamiprid']);ax.set(xlim=(0,330),ylim=(1.55,-.55),xlabel='Tested tomato samples');ax.set_xticks([0,158,316])
    fig.subplots_adjust(left=.10,right=.97,top=.94,bottom=.18)
    fig.canvas.draw()
    from matplotlib.text import Text
    renderer=fig.canvas.get_renderer();width,height=fig.canvas.get_width_height()
    clipped=[];undrawn_tick_labels=set()
    for ax in fig.axes:
        for axis,limits in [(ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())]:
            lo,hi=sorted(limits)
            for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                # Matplotlib creates log ticks outside view limits but does not paint them.
                if not lo<=tick.get_loc()<=hi:undrawn_tick_labels.update([tick.label1,tick.label2])
    for text in fig.findobj(match=Text):
        if text not in undrawn_tick_labels and text.get_visible() and text.get_text().strip():
            bb=text.get_window_extent(renderer)
            if bb.x0<0 or bb.y0<0 or bb.x1>width or bb.y1>height:clipped.append(text.get_text())
    assert not clipped,('Text outside figure canvas',clipped)
    for ext in ['svg','pdf','png']:fig.savefig(a.out/('figure_3_disclosure.'+ext),facecolor='white')
    Image.open(a.out/'figure_3_disclosure.png').convert('RGB').save(a.out/'figure_3_disclosure.tiff',compression='tiff_lzw',dpi=(600,600))
    svg=(a.out/'figure_3_disclosure.svg').read_text();assert '<text' in svg and '<image' not in svg and all('id="panel_'+c+'"' in svg for c in 'ABCDEFGH')
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    inputs=['eat2_whole_and_vegetable_denominators.csv','eat2_group_chemical_coverage.csv','eati_censor_threshold_distribution.csv','eati_source_interval_examples.csv','nz_difference_endpoint_counts.csv','reassessment_summary.json','brazil_two_pair_feasibility.json']
    (a.out/'figure_validation.json').write_text(json.dumps({'panels':['3'+c for c in 'ABCDEFGH'],'inputs':{n:sha(a.data/n) for n in inputs},'generation_code_sha256':sha(Path(__file__)),
      'figure_mm':[182.88,168.91],'vector_editable_text':True,'quantitative_only':True,'new_exposure_units':0,'SVG_raster_images':0,'text_clipping_check':'All visible labels/legends within canvas','six_examples':'First two records in source order per status, not selected extremes',
      'boundary':'Retrospective source diagnostics; not national prevalence, true-concentration confidence intervals, exposure or independent reviewer performance'},indent=2))
if __name__=='__main__':main()
