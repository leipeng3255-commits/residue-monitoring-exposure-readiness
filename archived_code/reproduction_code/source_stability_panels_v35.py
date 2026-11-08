"""Six quantitative source-stability panels. No raw access or new exposure model."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.ticker import PercentFormatter
import numpy as np
from PIL import Image
import yaml

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load((a.data / 'paths.yaml').read_text())
    assert cfg.get('mode') == 'saved_derived_replay_only'
    a.out.mkdir(parents=True, exist_ok=False)
    inputs = {}
    def read(name):
        p = a.data / 'source_stability_v35' / name
        inputs['source_stability_v35/' + name] = sha(p)
        return list(csv.DictReader(p.open()))
    codes = read('pdp/all_common_code_dispositions.csv')
    comparisons = read('pdp/eligible_comparisons.csv')
    joint = read('nz/nz_q1_joint_decision_matrix.csv')
    jam = read('nz/nz_jam_captan_plot_endpoints.csv')
    assert len(codes) == 362 and len(comparisons) == 56 and len(joint) == 16 and len(jam) == 4
    admitted = 'ELIGIBLE_SOURCE_CONDITIONAL'
    eligible = [r for r in codes if r['disposition'] == admitted]
    assert len(eligible) == 28
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
        'axes.labelsize': 8, 'axes.titlesize': 8.5, 'xtick.labelsize': 8,
        'ytick.labelsize': 8, 'legend.fontsize': 8, 'legend.frameon': False,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': .6,
        'svg.fonttype': 'none', 'pdf.fonttype': 42, 'svg.hashsalt': 'source-stability-v35',
        'savefig.dpi': 600})
    blue, orange, teal, grey = '#0072B2', '#B84A00', '#00856A', '#A9B1BA'
    fig, axes = plt.subplots(3, 2, figsize=(180/25.4, 224/25.4))
    axs = axes.ravel()
    fig.subplots_adjust(left=.18, right=.965, bottom=.08, top=.957, wspace=.72, hspace=.85)
    titles = ['PDP code-level admission', 'PDP tested-sample coverage',
              'PDP reporting-limit stability', 'PDP conditional reporting',
              'NZ repeated-Q1 decisions', 'NZ question-specific conflict']
    for letter, ax, title in zip('ABCDEF', axs, titles):
        ax.set_gid('panel_' + letter)
        ax.set_title(letter + '  ' + title, loc='left', fontweight='bold', pad=11)
        ax.tick_params(length=2.5, pad=2)
    plotted = []
    def point(panel, series, key, x, y, n=1, detail=''):
        plotted.append(dict(panel='4'+panel, series=series, key=key, x=x, y=y, n=n, detail=detail))
    # A retains every shared code. Hold reasons overlap; no sequential funnel.
    order = sorted(codes, key=lambda r: (r['disposition'] == admitted, r['hold_reasons'], r['code']))
    reasons = [('EXTRACTION_P90','P90 storage'), ('BQL_WITHOUT_NUMERIC_LOQ','BQL'),
               ('MARGINAL_NP','NP'), ('QUANTITATION_P','Quantitation P'),
               ('DETERMIN_METHOD_SET_CHANGED','Determination'), (admitted,'Admitted')]
    z = np.zeros((6, 362))
    labels = []
    for j, (key, label) in enumerate(reasons):
        for i, r in enumerate(order):
            present = (r['disposition'] == key) if key == admitted else key in r['hold_reasons'].split(';')
            z[j, i] = (2 if key == admitted else 1) if present else 0
            point('A', key, r['code'], i+1, j, int(present))
        labels.append(label + ' (' + str(int((z[j] > 0).sum())) + ')')
    ax = axs[0]
    ax.pcolormesh(z, cmap=ListedColormap(['#F0F2F4', grey, teal]), vmin=0, vmax=2,
                  shading='nearest', rasterized=False)
    ax.set(yticks=range(6), yticklabels=labels, xticks=[0,180,361], xticklabels=['1','181','362'],
           xlabel='Common codes (disposition-ordered)', ylim=(5.5,-.5))
    # B/C preserve all code coordinates, grouping only coincident points.
    for panel, ax, f1, f2 in [('B',axs[1],'coverage_2022','coverage_2023'),
                             ('C',axs[2],'lod_median_2022','lod_median_2023')]:
        for state, color, marker in [('HOLD',grey,'o'),(admitted,teal,'D')]:
            groups = Counter((float(r[f1]),float(r[f2])) for r in codes if r['disposition']==state)
            ax.scatter([p[0] for p in groups], [p[1] for p in groups],
                       s=[8+3*np.sqrt(n) for n in groups.values()], color=color, marker=marker,
                       edgecolor='white', linewidth=.35, alpha=.9,
                       label=('Held (334)' if state=='HOLD' else 'Admitted (28)'))
            for (x,y), n in groups.items(): point(panel,state,'coincident_coordinates',x,y,n)
        if panel=='B':
            ax.plot([0,1],[0,1],ls='--',color='#737D87',lw=.7)
            ax.set(xlim=(0,1.06),ylim=(0,1.06),xlabel='2022 tested / 709',ylabel='2023 tested / 708',
                   xticks=[0,.5,1],yticks=[0,.5,1])
            ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0))
            ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
            ax.legend(loc='upper left',bbox_to_anchor=(0,-.32),handletextpad=.3,labelspacing=.2)
        else:
            limits=[min(float(r[f]) for r in codes for f in [f1,f2])*.65,
                    max(float(r[f]) for r in codes for f in [f1,f2])*1.6]
            ax.plot(limits,limits,ls='--',color='#737D87',lw=.7)
            ax.set(xscale='log',yscale='log',xlim=limits,ylim=limits,
                   xlabel='2022 median LOD (ppm)',ylabel='2023 median LOD (ppm)')
    # D shows all eligible outcomes: 27 stable zero-report codes, plus the sole positive code.
    primary=[r for r in comparisons if r['threshold_multiplier']=='1']
    assert Counter(r['direction_comparison'] for r in primary)=={'stable_zero':27,'reversal':1}
    r1=next(r for r in primary if r['code']=='624')
    r2=next(r for r in comparisons if r['code']=='624' and r['threshold_multiplier']=='2')
    ax=axs[3]
    for year,color,marker in [('2022',blue,'o'),('2023',orange,'s')]:
        nums=[int(r1['native_numerator_'+year]),int(r1['threshold_numerator_'+year]),int(r2['threshold_numerator_'+year])]
        den=int(r1['native_denominator_'+year]); values=[100*n/den for n in nums]
        ax.plot(range(3),values,marker=marker,color=color,lw=1,label='THPI '+year,ms=4)
        for x,(n,v) in enumerate(zip(nums,values)):
            offset = (-22 if year=='2022' else 10) if x==1 else (10 if year=='2022' else -14)
            ax.annotate(f'{n}/{den}',(x,v),xytext=(0,offset),
                        textcoords='offset points',ha='center',fontsize=8,color=color)
            point('D','THPI_'+year,['native','T','2T'][x],x,v,detail=f'{n}/{den}')
    ax.scatter(range(3),[0,0,0],color='#333333',marker='+',s=48,zorder=5)
    for x in range(3): point('D','27_stable_zero_codes','all_other_eligible',x,0,27)
    ax.set(xticks=range(3),xticklabels=['Native','>T','>2T'],xlim=(-.35,2.35),ylim=(-.42,3.1),
           yticks=[0,1,2,3],xlabel='Reporting criterion (T = 0.024 ppm)',ylabel='Reported fraction (%)')
    ax.legend(loc='upper left',bbox_to_anchor=(-.03,-.32),handlelength=1.4,labelspacing=.2)
    ax.text(.98,.92,'Other 27 codes:\nzero reports in both years',transform=ax.transAxes,
            ha='right',va='top',fontsize=8)
    # E uses a logarithmic colour scale only; all zero cells are shown explicitly.
    ax=axs[4]; z=np.zeros((4,4),dtype=int)
    for r in joint:
        i,j=int(r['row_order'])-1,int(r['column_order'])-1; z[i,j]=int(r['keys'])
        point('E','joint_source_decisions',r['q1_65331_decision']+'|'+r['q1_in_70426_decision'],j,i,z[i,j])
    assert z.sum()==19422 and z[1,0]==1 and np.trace(z)==19421
    ax.pcolormesh(np.log10(z+1),cmap='cividis',vmin=0,vmax=np.log10(19427),shading='nearest',rasterized=False)
    for i in range(4):
        for j in range(4):
            ax.text(j,i,f'{z[i,j]:,}',ha='center',va='center',fontsize=8,
                    color='black' if z[i,j]>1000 else 'white',fontweight='bold' if (i,j)==(1,0) else 'normal')
    labels=['Above','Below','Unres.','Held']
    ax.set(xticks=range(4),xticklabels=labels,yticks=range(4),yticklabels=labels,ylim=(3.5,-.5),
           xlabel='Q1 in container 70426',ylabel='Q1 in container 65331')
    ax.text(.5,-.30,'Cell colour: log₁₀(count + 1)',transform=ax.transAxes,ha='center',fontsize=8)
    # F never pools these different questions; separate labelled rows preserve units.
    ax=axs[5]
    ordered=sorted(jam,key=lambda r:(r['estimand']!='Brand 1 minus Brand 2',r['source_id']))
    for y,r in enumerate(ordered):
        lo,hi=float(r['lower']),float(r['upper']); color=blue if r['source_id']=='65331' else orange
        ax.hlines(y,lo,hi,color=color,lw=2)
        ax.plot([lo,hi],[y,y],ls='',marker='|',ms=7,color=color)
        point('F',r['estimand'],r['source_id'],lo,hi,detail='Censoring endpoints, not confidence intervals')
    ax.axvline(0,color='#737D87',ls='--',lw=.7); ax.axhline(1.5,color='#D8DDE2',lw=.8)
    ax.set(yticks=range(4),yticklabels=['Difference\n65331','Difference\n70426','Mean\n65331','Mean\n70426'],
           ylim=(3.7,-.7),xlim=(-.05,.05),xticks=[-.04,0,.04],xlabel='Recorded endpoints (mg/kg)')
    ax.text(.5,-.31,'Jam / captan expression',transform=ax.transAxes,ha='center',fontsize=8)
    fig.canvas.draw(); renderer=fig.canvas.get_renderer(); box=fig.bbox
    bad=[]
    visible=[]
    for text in fig.findobj(matplotlib.text.Text):
        if not text.get_visible() or not text.get_text().strip(): continue
        # Ignore out-of-view log-locator labels, which are not painted by the axes.
        is_outside_tick=False
        for ax in axs:
            for axis,lim in [(ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())]:
                for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                    if text in [tick.label1,tick.label2] and not min(lim)<=tick.get_loc()<=max(lim): is_outside_tick=True
        if is_outside_tick: continue
        visible.append(text); bb=text.get_window_extent(renderer)
        if bb.x0<0 or bb.y0<0 or bb.x1>box.x1 or bb.y1>box.y1: bad.append(text.get_text())
    assert not bad, bad
    assert min(t.get_fontsize() for t in visible)>=8
    stem='figure_4_source_stability'
    for ext in ['svg','pdf','png']:
        meta={'Date':None} if ext=='svg' else {'CreationDate':None,'ModDate':None} if ext=='pdf' else None
        fig.savefig(a.out/(stem+'.'+ext),facecolor='white',metadata=meta)
    Image.open(a.out/(stem+'.png')).convert('RGB').save(a.out/(stem+'.tiff'),compression='tiff_lzw',dpi=(600,600))
    svg=(a.out/(stem+'.svg')).read_text(); assert '<text' in svg and '<image' not in svg
    with (a.out/'plotted_values.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(plotted[0]));writer.writeheader();writer.writerows(plotted)
    receipt=dict(panels=['4'+x for x in 'ABCDEF'],inputs=inputs,code_sha256=sha(Path(__file__)),
                 min_font_pt=8,figure_mm=[180,224],clipped_text=bad,editable_svg=True,
                 new_exposure_estimates=0,source_conditional=True,
                 outputs={p.name:sha(p) for p in a.out.iterdir() if p.is_file()})
    (a.out/'audit.json').write_text(json.dumps(receipt,indent=2))
    plt.close(fig);print(json.dumps(dict(out=str(a.out),panels=6,clipped_text=bad)))

if __name__=='__main__':
    main()
