"""Replay current Figures 1, 2, S1 and S3 from saved tables, not PRIMo. No raw files or network are accessed.

Usage: python portable_replay_v27.py --package PATH --out NEW_DIRECTORY
Dependencies: Python 3.10+, matplotlib, numpy, PyYAML, Pillow.
"""
import argparse, csv, hashlib, json, math, re
from collections import Counter
from pathlib import Path
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();base=args.package.resolve();out=args.out.resolve()
    assert not out.exists(), 'Use a fresh output directory; never overwrite user files'
    config=yaml.safe_load((base/'paths.yaml').read_text())
    tables=base/config['tables'];provenance=base/config['provenance']
    out.mkdir(parents=True)
    inputs={}
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def read(name):
        p=tables/name;inputs[str(p.relative_to(base))]=sha(p)
        with p.open() as f:return list(csv.DictReader(f))
    def js(name):
        p=provenance/name;inputs[str(p.relative_to(base))]=sha(p);return json.loads(p.read_text())
    cells=read('cell_diagnostics.csv');strict=read('strict_37_ledger.csv');admission=read('admission_decision_ledger.csv')
    surveys=read('dietary_strata.csv');subsets=read('robustness_subsets.csv');ratios=read('same_chemical_ratio_bounds.csv')
    limits=read('nondetect_limit_distribution.csv');master=read('chronic_exposure_master.csv')
    assert (len(cells),len(strict),len(admission),len(surveys),len(master))==(19,37,262,88,1672)
    errors=[]
    for r in master:
        for stat in ['mean','HRP']:
            for end in ['LB','UB']:
                a=float(r[f'exposure_{stat}_{end}_ug_kg_bw_day'])/(10*float(r['adi_mg_kg_bw_day']))
                b=float(r[f'percent_ADI_{stat}_{end}']);assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12);errors.append(abs(a-b))
    bykey={(r['occurrence_country'],r['pesticide']):r for r in cells}
    for r in ratios:
        a,b=bykey[('CZ',r['pesticide'])],bykey[('DE',r['pesticide'])]
        assert math.isclose(float(r['ratio_lower']),float(a['occurrence_LB'])/float(b['occurrence_UB']),rel_tol=1e-12)
        assert math.isclose(float(r['ratio_upper']),float(a['occurrence_UB'])/float(b['occurrence_LB']),rel_tol=1e-12)
    # Historical disclosure Figure 3 is not part of this current four-figure route.
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,'axes.labelsize':8,
      'xtick.labelsize':7.5,'ytick.labelsize':7.5,'axes.spines.top':False,'axes.spines.right':False,
      'axes.linewidth':.65,'legend.frameon':False,'legend.fontsize':7,'svg.fonttype':'none','pdf.fonttype':42,
      'svg.hashsalt':'govh-final-v19','savefig.dpi':600})
    BLUE,ORANGE,GREY,INK='#0072B2','#D55E00','#B6BDC4','#30343B'
    registry=[]
    def panel(ax,letter,title):ax.set_gid('panel_'+letter);ax.set_title(letter+'  '+title,loc='left',weight='bold',pad=12)
    def save(fig,stem,panels):
        files=[]
        for ext in ['svg','pdf','png']:
            p=out/(stem+'.'+ext);fig.savefig(p,bbox_inches='tight',facecolor='white')
            if ext=='svg':
                s=p.read_text();assert '<text' in s and '<image' not in s
                assert all('id="panel_'+x+'"' in s for x in panels)
            files.append({'name':p.name,'sha256':sha(p)})
        im=Image.open(out/(stem+'.png')).convert('RGB');im.save(out/(stem+'.tiff'),compression='tiff_lzw',dpi=(600,600))
        registry.append({'stem':stem,'panels':list(panels),'files':files});plt.close(fig)

    fig=plt.figure(figsize=(7.2,5.7));gs=fig.add_gridspec(2,2,height_ratios=[1,1.15],hspace=.68,wspace=.95)
    a,b,c=fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,:])
    panel(a,'A','Admission audit (262 units)')
    # Current disposition comes from the admission ledger, not historical strict-ledger fields.
    counts=Counter(r['current_classification'] for r in admission)
    v=[counts[x] for x in ['PRIMARY_MACP_ADMISSIBLE','HOLD','EXCLUDE']]
    assert v==[19,199,44]
    a.barh(range(3),v,color=[BLUE,GREY,GREY],height=.48)
    a.set_yticks(range(3),['Admitted','Held','Below support rule']);a.invert_yaxis();a.set(xlim=(0,225),xlabel='Candidate units')
    for i,n in enumerate(v):a.text(n+3,i,str(n),va='center',fontsize=8)
    panel(b,'B','Residue definition (37 units)')
    cc=Counter(r['residue_definition_status'] for r in strict)
    v=[cc[x] for x in ['RD_EXACT','RD_CONVERSION_AVAILABLE','RD_MISMATCH_NO_CONVERSION','RD_UNRESOLVED']]
    assert v==[18,1,10,8]
    b.barh(range(4),v,color=[BLUE,BLUE,GREY,GREY],height=.5)
    b.set_yticks(range(4),['Exact match','Expression conversion','Mismatch; no conversion','Unresolved']);b.invert_yaxis();b.set(xlim=(0,21),xlabel='Strict MACP units')
    for i,n in enumerate(v):b.text(n+.3,i,str(n),va='center',fontsize=8)
    panel(c,'C','Sample support within the 37-unit set')
    for admitted,label,col,marker in [(False,'Held',GREY,'s'),(True,'Admitted',BLUE,'o')]:
        rows=[r for r in strict if (r['residue_definition_status'] in ['RD_EXACT','RD_CONVERSION_AVAILABLE'])==admitted]
        points=Counter((int(r['sample_n']),100*int(r['quantified_n'])/int(r['sample_n'])) for r in rows)
        c.scatter([p[0] for p in points],[p[1] for p in points],s=[25*n for n in points.values()],c=col,marker=marker,label=label,edgecolors='white',linewidths=.4)
    c.set(xlabel='Tested samples per unit',ylabel='Quantified results (%)',xlim=(0,230),ylim=(0,48));c.legend(loc='upper right',ncol=2)
    save(fig,'figure_1_qualification','ABC')

    ds=sorted(cells,key=lambda r:float(r['max_mean_percent_ADI_UB']),reverse=True)
    fig=plt.figure(figsize=(7.2,8));gs=fig.add_gridspec(2,2,height_ratios=[2.5,1],width_ratios=[1.6,1],hspace=.48,wspace=.43)
    a,b,c=fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,:])
    panel(a,'A','Single-food contributions');panel(b,'B','Same-chemical ratio bounds')
    for i,r in enumerate(ds):a.plot([float(r['max_mean_percent_ADI_LB']),float(r['max_mean_percent_ADI_UB'])],[i,i],color=BLUE,lw=1.3)
    a.scatter([float(r['max_mean_percent_ADI_UB']) for r in ds],range(19),c=BLUE,s=14,label='Survey-mean UB')
    a.scatter([float(r['max_native_HRP_percent_ADI_UB']) for r in ds],range(19),facecolors='white',edgecolors=INK,s=22,marker='D',label='Native high-percentile UB')
    a.set_yticks(range(19),[r['occurrence_country']+'  '+r['pesticide'] for r in ds]);a.set_ylim(18.8,-.8);a.set_xscale('log')
    a.set_xlabel('ADI (%) · logarithmic scale');a.set_xticks([.0001,.001,.01,.1,1,10],['0.0001','0.001','0.01','0.1','1','10'])
    fig.legend(*a.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.6,1.015),ncol=2)
    for i,r in enumerate(ratios):
        low,high=float(r['ratio_lower']),float(r['ratio_upper']);col=ORANGE if low<=1<=high else BLUE
        b.plot([low,high],[i,i],color=col,lw=2);b.scatter([low,high],[i,i],marker='|',color=col,s=70)
        b.text(.5,i+.24,f'{low:.2f}–{high:.2f}',transform=b.get_yaxis_transform(),ha='center',fontsize=8)
    b.axvline(1,color=INK,lw=.8,ls='--');b.set_xscale('log');b.set(xlim=(.3,20),ylim=(2.55,-.45),xlabel='CZ / DE mean ratio · log scale')
    b.set_yticks(range(3),[r['pesticide'].capitalize() for r in ratios]);b.set_xticks([.5,1,2,5,10],['0.5','1','2','5','10'])
    b.text(.5,-.15,'Censoring only; not confidence intervals',transform=b.transAxes,ha='center',fontsize=6.8)
    for ax in [a,b]:ax.grid(axis='x',color='#E4E7EA',lw=.5);ax.set_axisbelow(True)
    panel(c,'C','Dietary-survey age at the 2022 occurrence snapshot')
    gaps=Counter(int(float(r['survey_gap_to_monitoring_years'])) for r in surveys)
    c.bar(sorted(gaps),[gaps[k] for k in sorted(gaps)],width=.7,color=BLUE)
    c.set(xlabel='2022 − dietary survey end year',ylabel='Dietary strata',xticks=range(10,23,2),ylim=(0,max(gaps.values())+3));c.yaxis.set_major_locator(MaxNLocator(integer=True))
    for x,n in sorted(gaps.items()):c.text(x,n+.25,str(n),ha='center',fontsize=7)
    fig.subplots_adjust(left=.26,right=.99,top=.93,bottom=.08);save(fig,'figure_2_primo','ABC')

    fig,(a,b)=plt.subplots(2,1,figsize=(7.2,5.8),gridspec_kw={'hspace':.72,'height_ratios':[1.2,1]})
    panel(a,'A','Reporting limits in entirely below-LOQ records')
    chems=['Cyazofamid','Mandipropamid'];bottom=np.zeros(2);means=[]
    for lim,col,hatch in [(.001,BLUE,None),(.005,ORANGE,'///'),(.01,GREY,None)]:
        vals=[sum(int(r['sample_chemical_records']) for r in limits if r['chemical']==ch and float(r['LOQ_mg_kg'])==lim) for ch in chems]
        a.barh(range(2),vals,left=bottom,color=col,height=.45,hatch=hatch,edgecolor='white',linewidth=.6,label=f'{lim:g} mg/kg')
        for i,n in enumerate(vals):
            if n>=10:a.text(bottom[i]+n/2,i,str(n),ha='center',va='center',color='white' if lim==.001 else INK)
            elif n:a.annotate(str(n),(bottom[i]+n/2,i),xytext=(0,-26),textcoords='offset points',ha='center',fontsize=7,arrowprops={'arrowstyle':'-','lw':.5})
        bottom+=vals
    assert list(bottom)==[214,214]
    a.set_yticks(range(2),chems);a.set(xlabel='Sample–chemical records',xlim=(0,220),ylim=(1.65,-.55));a.legend(title='Recorded LOQ',loc='upper center',bbox_to_anchor=(.5,-.28),ncol=3,title_fontsize=7)
    panel(b,'B','Monitored-expression means remain bounded')
    for i,ch in enumerate(chems):
        u=sum(float(r['LOQ_mg_kg'])*int(r['sample_chemical_records']) for r in limits if r['chemical']==ch)/214
        b.plot([0,u],[i,i],c=BLUE,lw=2);b.scatter([0,u],[i,i],c=BLUE,s=18);b.text(u+.00012,i,f'{u:.6f}',va='center',fontsize=8)
    b.set_yticks(range(2),chems);b.set(xlim=(-.0001,.0101),ylim=(1.6,-.6),xlabel='Mean concentration interval (mg/kg)');b.grid(axis='x',color='#E4E7EA',lw=.5);b.set_axisbelow(True)
    fig.subplots_adjust(left=.2,right=.98,top=.93,bottom=.11);save(fig,'figure_S3_information','AB')

    fig,(a,b)=plt.subplots(1,2,figsize=(7.2,3.4),gridspec_kw={'width_ratios':[1,1.25]})
    labels=['Exact definition only','Exact + converted (primary)','Tested samples ≥50','Quantified fraction ≥10%','Survey end year ≥2010'];y=np.arange(5)
    panel(a,'A','Retained occurrence units');panel(b,'B','Largest survey-mean UB')
    a.scatter([int(r['cells']) for r in subsets],y,c=BLUE,s=24);b.scatter([float(r['max_mean_percent_ADI_UB']) for r in subsets],y,c=BLUE,s=24)
    for i,r in enumerate(subsets):
        a.annotate(r['cells'],(int(r['cells']),i),xytext=(5,0),textcoords='offset points',va='center',fontsize=7)
        b.annotate(f"{float(r['max_mean_percent_ADI_UB']):.4f}",(float(r['max_mean_percent_ADI_UB']),i),xytext=(5,0),textcoords='offset points',va='center',fontsize=7)
    a.set_yticks(y,labels);b.set_yticks(y,[]);a.set(xlim=(0,23),xlabel='Occurrence units');b.set(xlim=(0,4.8),xlabel='ADI (%)')
    for ax in [a,b]:ax.set_ylim(4.6,-.6);ax.grid(axis='x',lw=.5,color='#E4E7EA');ax.set_axisbelow(True)
    fig.subplots_adjust(left=.31,right=.98,wspace=.3,bottom=.2,top=.86);save(fig,'figure_S1_subsets','AB')
    receipt={'inputs':inputs,'figures':registry,'percent_ADI_checks':len(errors),'maximum_absolute_conversion_error':max(errors),'new_exposure_scenarios':0}
    (out/'replay_validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'figures':len(registry),'panels':sum(len(r['panels']) for r in registry),'arithmetic_checks':len(errors)}))

if __name__=='__main__':main()

