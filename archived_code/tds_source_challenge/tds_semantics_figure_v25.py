"""Portable aggregate-only replacement for Figure 3; no raw or exposure modelling."""
import argparse,csv,hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert not a.out.exists();a.out.mkdir(parents=True)
    source=json.loads((a.data/'source_summary.json').read_text());rows=list(csv.DictReader((a.data/'eat2_chemical_denominator_bounds.csv').open()))
    brazil=json.loads((a.data/'brazil_two_pair_feasibility.json').read_text())
    fr={r['source']:r for r in source['sources']}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,
        'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'legend.frameon':False,'legend.fontsize':7,'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'tds-semantics-v25','savefig.dpi':300})
    blue,orange,grey,ink='#0072B2','#D55E00','#B6BDC4','#30343B'
    fig=plt.figure(figsize=(7.2,6.4));gs=fig.add_gridspec(2,2,height_ratios=[1.3,1],hspace=.8,wspace=.7)
    aa,bb,cc=fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,:])
    def panel(ax,l,t):ax.set_gid('panel_'+l);ax.set_title(l+'  '+t,loc='left',weight='bold',pad=12)
    panel(aa,'A','Blank fields have different meanings')
    e2,e1=fr['EAT2']['cell_states'],fr['EATi']['cell_states']
    counts=[[e2['n_unanalysed'],e2['n_ND']+e2['n_NQ'],e2['n_VAL']],[0,e1['<LD']+e1['<LQ'],e1['VAL']]]
    totals=[sum(r) for r in counts];assert totals==[384146,64112]
    for i,rr in enumerate(counts):
        left=0
        for j,x in enumerate(rr):
            aa.barh(i,x/totals[i],left=left,height=.32,color=[grey,blue,orange][j],edgecolor='white',linewidth=.4,label=['Not analysed','Censored result','Quantified'][j] if i==0 else None);left+=x/totals[i]
    aa.set(yticks=[0,1],yticklabels=['EAT2\n384,146 cells','EATi\n64,112 records'],xlim=(0,1),ylim=(1.55,-.5),xlabel='Share of the inspected source fields')
    aa.xaxis.set_major_formatter(PercentFormatter(1));aa.legend(loc='upper left',bbox_to_anchor=(-.18,-.3),ncol=1)
    aa.text(0,.26,'223,520 unanalysed; 691 quantified',fontsize=7,va='top')
    aa.text(0,1.26,'63,933 censored blanks; 179 quantified',fontsize=7,va='top')
    panel(bb,'B','Wrong zero-filled denominator')
    factors=sorted(float(r['denominator_attenuation_factor']) for r in rows);assert len(factors)==322
    bb.step(factors,[100*(i+1)/len(factors) for i in range(len(factors))],where='post',color=blue,lw=1.4)
    med=float(fr['EAT2']['factor_median']);bb.axvline(med,color=orange,lw=.9,ls='--')
    bb.annotate(f'Median: {med:.1%}',xy=(med,50),xytext=(.55,32),arrowprops={'arrowstyle':'-','lw':.7},fontsize=8)
    bb.set(xlim=(0,1.02),ylim=(0,103),xlabel='Wrong / tested-record mean endpoint',ylabel='Cumulative chemical columns (%)')
    bb.xaxis.set_major_formatter(PercentFormatter(1));bb.text(0,-.38,'322 chemical columns; factor = n_tested / 1,193\nPositive endpoints only; no dietary weighting',transform=bb.transAxes,fontsize=7,va='top')
    panel(cc,'C','PARA: documented analyte-tested denominators')
    parts=[]
    for k in ['Acefato','Acetamiprido']:
        r=brazil['pairs'][k];cl=r['reporting_classes'];parts.append([cl.get('NUMERIC_REPORTED',0),cl.get('DETECTED_BELOW_QUANTIFICATION',0),r['samples_without_listed_target_result']])
    bottom=[0,0]
    for j,(label,col,hatch) in enumerate([('Numeric detection',blue,None),('Detected below LOQ',orange,'///'),('Aggregate non-detection',grey,None)]):
        vals=[r[j] for r in parts];cc.barh([0,1],vals,left=bottom,height=.42,color=col,hatch=hatch,edgecolor='white',linewidth=.5,label=label)
        for i,n in enumerate(vals):
            if not n:continue
            if n<20:cc.annotate(str(n),(bottom[i]+n/2,i),xytext=(0,-18),textcoords='offset points',ha='center',fontsize=7,arrowprops={'arrowstyle':'-','lw':.6})
            else:cc.text(bottom[i]+n/2,i,str(n),ha='center',va='center',fontsize=8,color='white' if j==0 else ink)
        bottom=[x+y for x,y in zip(bottom,vals)]
    assert bottom==[316,316];cc.set(yticks=[0,1],yticklabels=['Acephate','Acetamiprid'],xlim=(0,330),ylim=(1.6,-.6),xlabel='Tested samples per analyte');cc.legend(loc='upper center',bbox_to_anchor=(.5,-.32),ncol=3)
    fig.subplots_adjust(left=.16,right=.98,top=.93,bottom=.17)
    for ext in ['svg','pdf','png']:fig.savefig(a.out/('figure_3_disclosure.'+ext),bbox_inches='tight',facecolor='white')
    Image.open(a.out/'figure_3_disclosure.png').convert('RGB').save(a.out/'figure_3_disclosure.tiff',compression='tiff_lzw',dpi=(300,300))
    svg=(a.out/'figure_3_disclosure.svg').read_text();assert '<text' in svg and '<image' not in svg and all('id="panel_'+x+'"' in svg for x in 'ABC')
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    receipt={'panels':['3A','3B','3C'],'input_sha256':{p:sha(a.data/p) for p in ['source_summary.json','eat2_chemical_denominator_bounds.csv','brazil_two_pair_feasibility.json']},
             'script_sha256':sha(Path(__file__)),'exports':[{'file':p.name,'sha256':sha(p)} for p in a.out.iterdir() if p.is_file()],
             'scope':'Source semantics/denominator experiment, not exposure, programme ranking or independent validation'}
    (a.out/'figure_validation.json').write_text(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
