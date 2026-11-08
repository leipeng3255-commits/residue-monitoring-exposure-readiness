"""Editable v30 Figures 1, 2 and 4 from sealed v29 aggregates; no exposure model.

Portable: --data PACKAGE/03_... --out NEW_DIRECTORY. Project default reads paths.yaml.
"""
import argparse, csv, hashlib, json
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import numpy as np
import yaml

BLUE, ORANGE, GREY, INK, TEAL = '#0072B2', '#D55E00', '#B9C1C9', '#28343D', '#009E73'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
 'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,
 'legend.frameon':False,'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'v30',
 'savefig.facecolor':'white'})

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def panel(ax, letter, title):
    ax.set_gid('panel_'+letter)
    ax.set_title(letter+'  '+title,loc='left',fontweight='bold',pad=12)

def matrix(ax,z,**kwargs):
    h,w=z.shape
    ax.pcolormesh(np.arange(w+1)-.5,np.arange(h+1)-.5,z,**kwargs)
    ax.set(xlim=(-.5,w-.5),ylim=(h-.5,-.5))

def build(data, out):
    out.mkdir(parents=True,exist_ok=False)
    inputs={}; figures=[]
    def read(rel):
        p=data/rel; inputs[rel]=sha(p)
        return json.loads(p.read_text()) if p.suffix=='.json' else list(csv.DictReader(p.open()))
    def table(name): return read('tables/'+name+'.csv')
    def save(fig,stem,letters,caption,sources):
        fig.canvas.draw()
        # Check every visible text's outer boundary at the chosen physical size.
        bad=[]; renderer=fig.canvas.get_renderer(); box=fig.bbox
        ticks={id(t) for ax in fig.axes for t in ax.get_xticklabels()+ax.get_yticklabels()}
        for txt in fig.findobj(matplotlib.text.Text):
            if not txt.get_visible() or not txt.get_text(): continue
            if id(txt) in ticks: continue # final PDF QA checks rendered ticks, not out-of-view locators
            bb=txt.get_window_extent(renderer)
            if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > box.x1+1 or bb.y1 > box.y1+1: bad.append(txt.get_text())
        assert not bad,(stem,bad)
        for ext in ['svg','pdf','png','tiff']:
            fig.savefig(out/(stem+'.'+ext),dpi=600,**({'pil_kwargs':{'compression':'tiff_lzw'}} if ext=='tiff' else {}))
        text=(out/(stem+'.svg')).read_text()
        assert '<image' not in text and '<text' in text
        assert all('id="panel_'+x+'"' in text for x in letters)
        figures.append({'stem':stem,'panels':list(letters),'caption':caption,'source_by_panel':sources,
                        'physical_inches':list(fig.get_size_inches()),'text_outside_canvas':bad})
        plt.close(fig)

    ad=table('admission_decision_ledger'); st=table('strict_37_ledger')
    au=table('target_conditioned_audit_37'); grid=table('support_threshold_grid')
    assert (len(ad),len(st),len(au),len(grid))==(262,37,37,20)
    fig=plt.figure(figsize=(7.2,8.65))
    gs=fig.add_gridspec(3,2,left=.17,right=.975,bottom=.10,top=.955,wspace=.92,hspace=.78,
                        height_ratios=[.9,1.2,1])
    a,b,c,d,e,f=[fig.add_subplot(gs[i//2,i%2]) for i in range(6)]
    panel(a,'A','Candidate dispositions')
    for i,(status,label,col) in enumerate([('PRIMARY_MACP_ADMISSIBLE','Admitted',BLUE),('HOLD','Held',GREY),('EXCLUDE','Below support\nrule',ORANGE)]):
        n=sum(r['current_classification']==status for r in ad)
        a.barh(i,n,color=col,height=.48);a.text(n+4,i,str(n),va='center')
    a.set(yticks=range(3),yticklabels=['Admitted','Held','Below support\nrule'],xlim=(0,235),xlabel='Units (n = 262)');a.invert_yaxis()
    panel(b,'B','Chemical compatibility')
    values=[sum(r['residue_definition_status']==s for r in st) for s in ['RD_EXACT','RD_CONVERSION_AVAILABLE','RD_MISMATCH','RD_UNRESOLVED']]
    # Historical ledger uses RD_MISMATCH_NO_CONVERSION, not a fuzzy match.
    values[2]=sum(r['residue_definition_status'].startswith('RD_MISMATCH') for r in st)
    assert values==[18,1,10,8],values
    b.barh(range(4),values,color=[BLUE,TEAL,GREY,GREY],height=.5)
    for i,n in enumerate(values): b.text(n+.35,i,str(n),va='center')
    b.set(yticks=range(4),yticklabels=['Exact','Converted','Mismatch','Unresolved'],xlim=(0,21),xlabel='Strict MACP units (n = 37)');b.invert_yaxis()
    panel(c,'C','Sampling support')
    for yes,lab,col,mark in [(False,'Held',GREY,'s'),(True,'Admitted',BLUE,'o')]:
        rs=[r for r in st if (r['residue_definition_status'] in ['RD_EXACT','RD_CONVERSION_AVAILABLE'])==yes]
        points=Counter((int(r['sample_n']),100*int(r['quantified_n'])/int(r['sample_n'])) for r in rs)
        c.scatter([x[0] for x in points],[x[1] for x in points],s=[16*v for v in points.values()],color=col,marker=mark,edgecolor='white',lw=.4,label=lab)
    c.set(xlim=(0,235),ylim=(0,50),xlabel='Tested samples / unit',ylabel='Quantified results (%)');c.legend(loc='upper right',handletextpad=.4)
    panel(d,'D','Selected candidate frame')
    markets=sorted({r['reporting_country'] for r in ad}); y=np.arange(len(markets))
    foods=sorted({r['vegetable'] for r in ad}); assert len(foods)==2
    left=np.zeros(len(markets))
    for food,col in zip(foods,[GREY,BLUE]):
        v=[sum(r['reporting_country']==m and r['vegetable']==food for r in ad) for m in markets]
        d.barh(y,v,left=left,height=.65,color=col,label='Peppers' if 'pepper' in food.lower() else 'Tomatoes');left+=v
    d.set(yticks=y,yticklabels=markets,xlabel='Candidate units');d.invert_yaxis()
    d.set_ylim(len(markets)-.5,-3.5)
    d.legend(loc='upper right',bbox_to_anchor=(1,1.02),fontsize=8)
    panel(e,'E','Question-specific evidence')
    au=sorted(au,key=lambda r:(r['native_paired_output']!='VERIFIED_SAVED_PAIR',r['unit']))
    keys=['numeric_censor_limits','chemical_sample_aggregate_validation','native_paired_output','historical_raw_RPC_scenario','contemporary_population_exposure']
    good=['DOCUMENTED_COMPLETE','SUPPORTED_FOR_SAVED_APPLICATION','VERIFIED_SAVED_PAIR','SUPPORTED_WITH_DOCUMENTED_ADAPTATION','NEVER_SUPPORTED']
    z=np.array([[1 if r[k]==v else 0 for r in au] for k,v in zip(keys,good)])
    e.pcolormesh(np.arange(38),np.arange(6),z,cmap=ListedColormap(['#EDF0F3',BLUE]),vmin=0,vmax=1,edgecolors='white',lw=.25)
    e.set(yticks=np.arange(5)+.5,yticklabels=['Numeric limits','Chemical basis','Paired output','Historical target','Current target'],xticks=[.5,9.5,18.5,27.5,36.5],xticklabels=[1,10,19,28,37],xlabel='Ordered units (key in source table)',ylim=(5,0))
    e.axvline(19,color=INK,lw=.9)
    fig.legend(handles=[Patch(facecolor=BLUE,label='Documented for target (E)'),Patch(facecolor='#EDF0F3',edgecolor=GREY,label='Not established / not released (E)')],loc='lower center',bbox_to_anchor=(.52,.005),ncol=2,fontsize=8,handlelength=1)
    panel(f,'F','Support-rule sensitivity')
    ns=sorted({int(r['minimum_samples']) for r in grid});qs=sorted({int(r['minimum_quantified_results']) for r in grid})
    z=np.array([[int(next(r for r in grid if int(r['minimum_samples'])==n and int(r['minimum_quantified_results'])==q)['current_chemical_subset_retained']) for q in qs] for n in ns])
    matrix(f,z,cmap='Blues',vmin=0,vmax=19)
    for i in range(len(ns)):
        for j in range(len(qs)): f.text(j,i,str(z[i,j]),ha='center',va='center',color='white' if z[i,j]>10 else INK)
    original=next(r for r in grid if r['original_support_setting']=='True')
    i=ns.index(int(original['minimum_samples']));j=qs.index(int(original['minimum_quantified_results']))
    f.add_patch(Rectangle((j-.48,i-.48),.96,.96,fill=False,color=ORANGE,lw=1.7))
    f.set(xticks=range(len(qs)),xticklabels=qs,yticks=range(len(ns)),yticklabels=ns,xlabel='Minimum quantified results',ylabel='Minimum tested samples')
    save(fig,'figure_1_qualification','ABCDEF',
      'Qualification is conditional on the question and selected frame. (A) Current dispositions of 262 candidates. (B) Chemical compatibility in 37 strict MACP units. (C) Tested counts and quantified fractions; marker area preserves coincident-unit multiplicity without jitter. (D) The selected 13-market, two-food candidate frame; no national coverage inference. (E) Five recorded evidence states across 37 units, ordered with 19 admitted units first; grey means not established or not released, not measured failure. Complete limits alone do not establish a current-population target. The unit key is supplied with plot data. (F) Numbers of the current 19-unit chemical subset retained by 20 study-specific support settings; orange marks the original setting. This is a selection sensitivity, not a universal readiness threshold or new admission. The separate 305,320-record domain is not the denominator of A.',
      {'A':['tables/admission_decision_ledger.csv'],'B':['tables/strict_37_ledger.csv'],'C':['tables/strict_37_ledger.csv'],'D':['tables/admission_decision_ledger.csv'],'E':['tables/target_conditioned_audit_37.csv'],'F':['tables/support_threshold_grid.csv']})
    with (out/'figure1E_ordered_unit_key.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=['plot_position']+list(au[0]));w.writeheader();w.writerows(dict(plot_position=i+1,**r) for i,r in enumerate(au))

    cells=table('cell_diagnostics'); ratios=table('same_chemical_ratio_bounds'); surveys=table('dietary_strata')
    az=table('azoxystrobin_reference_sensitivity'); subsets=table('robustness_subsets')
    assert (len(cells),len(ratios),len(surveys),len(az),len(subsets))==(19,3,88,176,5)
    fig=plt.figure(figsize=(7.2,9.7))
    gs=fig.add_gridspec(4,2,left=.24,right=.97,bottom=.065,top=.95,wspace=.94,hspace=1.00,height_ratios=[1.05,1.05,1.05,.85])
    a=fig.add_subplot(gs[:2,0]);b=fig.add_subplot(gs[0,1]);c=fig.add_subplot(gs[1,1]);d=fig.add_subplot(gs[2,0]);e=fig.add_subplot(gs[2,1]);f=fig.add_subplot(gs[3,:])
    panel(a,'A','Single-food contributions')
    ds=sorted(cells,key=lambda r:float(r['max_mean_percent_ADI_UB']),reverse=True)
    for i,r in enumerate(ds):
        a.plot([float(r['max_mean_percent_ADI_LB']),float(r['max_mean_percent_ADI_UB'])],[i,i],color=BLUE,lw=1.2)
    a.scatter([float(r['max_mean_percent_ADI_UB']) for r in ds],range(19),s=14,color=BLUE,label='Mean UB')
    a.scatter([float(r['max_native_HRP_percent_ADI_UB']) for r in ds],range(19),s=20,facecolor='white',edgecolor=INK,marker='D',label='Native HRP UB')
    a.set(yticks=range(19),yticklabels=[r['occurrence_country']+' '+r['pesticide'] for r in ds],ylim=(18.7,-.8),xscale='log',xlabel='ADI (%) · log scale',xticks=[.0001,.01,1],xticklabels=['0.0001','0.01','1'])
    a.legend(loc='upper left',bbox_to_anchor=(-.12,-.10),ncol=2,fontsize=8,handlelength=1,columnspacing=.5)
    a.grid(axis='x',color='#E6E9EC',lw=.5)
    panel(b,'B','Within-chemical ratios')
    for i,r in enumerate(ratios):
        lo,hi=float(r['ratio_lower']),float(r['ratio_upper']);b.plot([lo,hi],[i,i],color=BLUE,lw=1.6,marker='|',ms=7)
    b.axvline(1,color=INK,lw=.7,ls='--');b.set(yticks=range(3),yticklabels=[r['pesticide'] for r in ratios],ylim=(2.6,-.6),xscale='log',xlim=(.35,18),xticks=[.5,1,5,10],xticklabels=['0.5','1','5','10'],xlabel='CZ / DE mean (log scale)')
    panel(c,'C','Dietary-survey age')
    gaps=Counter(int(float(r['survey_gap_to_monitoring_years'])) for r in surveys)
    c.bar(sorted(gaps),[gaps[k] for k in sorted(gaps)],color=BLUE,width=.7)
    c.set(xlabel='2022 − survey end year',ylabel='Strata (n = 88)',xticks=[10,14,18,22])
    panel(d,'D','One chemical, 88 diets')
    for market,col in [('CZ',BLUE),('DE',ORANGE)]:
        v=sorted(float(r['EFSA_mean_percent_ADI_UB']) for r in az if r['occurrence_country']==market)
        d.step(v,np.arange(1,len(v)+1)/len(v),where='post',color=col,label=market,ls='-' if market=='CZ' else '--')
    d.set(xscale='log',xlabel='Azoxystrobin mean UB (% ADI)',ylabel='Fraction of strata',ylim=(0,1.04));d.legend(loc='lower right')
    panel(e,'E','ADI sensitivity')
    for market,col,marker in [('CZ',BLUE,'o'),('DE',ORANGE,'s')]:
        rs=[r for r in az if r['occurrence_country']==market]
        e.scatter([float(r['EFSA_mean_percent_ADI_UB']) for r in rs],[float(r['JMPR_mean_percent_ADI_UB']) for r in rs],s=9,color=col,marker=marker,alpha=.65)
    v=np.array([min(float(r['EFSA_mean_percent_ADI_UB']) for r in az),max(float(r['JMPR_mean_percent_ADI_UB']) for r in az)])
    e.plot(v,v,color=GREY,lw=.7,ls='--');e.set(xscale='log',yscale='log',xlabel='EFSA ADI 0.2: mean UB (%)',ylabel='JMPR ADI 0.03: mean UB (%)')
    panel(f,'F','Restrictions change the displayed subset')
    labs=['Exact only','Exact + converted','Tested n ≥ 50','Quantified ≥ 10%','Survey end ≥ 2010']
    for i,(r,lab) in enumerate(zip(subsets,labs)):
        f.plot([float(r['max_mean_percent_ADI_UB']),float(r['max_HRP_percent_ADI_UB'])],[i,i],color=GREY,lw=1)
        f.scatter(float(r['max_mean_percent_ADI_UB']),i,s=18,color=BLUE)
        f.scatter(float(r['max_HRP_percent_ADI_UB']),i,s=22,marker='D',facecolor='white',edgecolor=INK)
        f.text(13.5,i,f"{r['cells']} units; {r['rows']} rows",va='center',fontsize=8)
    f.set(yticks=range(5),yticklabels=labs,ylim=(4.5,-.5),xlim=(0,20),xticks=[0,4,8,12],xlabel='Maximum contribution (% ADI); symbols as in A')
    save(fig,'figure_2_primo','ABCDEF',
      'Saved PRIMo scenarios and their limits. (A) Nineteen market–chemical inputs: mean LB–UB segments, mean UB circles and native high-percentile UB diamonds. All displayed maxima occur in Bulgaria/NUTRICHILD toddlers; the native maximum is P97.5, although labels differ across profiles. (B) Same-chemical CZ/DE sampled-mean ratio bounds; sample counts are 18/214. Bounds exclude sampling and measurement uncertainty and are not confidence intervals. (C) Survey age for 88 strata sharing 33 surveys. (D) Azoxystrobin upper-mean contributions across those strata, with each occurrence market applied to all profiles. (E) The same 176 saved contributions under ADIs of 0.2 and 0.03 mg/kg bw/day; the 6.67-fold change is arithmetic rescaling, not a new exposure calculation. Dashed line: equality. (F) Saved subset restrictions; counts are occurrence inputs and repeated scenario rows. Segments connect two statistics, not uncertainty bounds. Changed maxima are composition effects, not interventions. Markets are not consumer populations; chemical-specific %ADI values are not a common disease-risk scale or evidence of total-diet safety.',
      {'A':['tables/cell_diagnostics.csv'],'B':['tables/same_chemical_ratio_bounds.csv'],'C':['tables/dietary_strata.csv'],'D':['tables/azoxystrobin_reference_sensitivity.csv'],'E':['tables/azoxystrobin_reference_sensitivity.csv'],'F':['tables/robustness_subsets.csv']})

    cases=read('comparator_v29/cases.json');cr=read('comparator_v29/case_results.csv');fs=read('comparator_v29/family_summary.csv')
    families=['single_food_mean_reference','same_chemical_CZ_DE_order','selected_production_group_order','known_source_examples','retargeted_current_population','artificial_boundaries']
    flabels=['Reference (19)','Market order (3)','Production (15)','Source (11)','New target (19)','Artificial (23)']
    by={(r['case_id'],r['arm']):r for r in cr}
    def code(result):return 2 if result.startswith('HOLD') else 1 if result=='CENSORING_UNRESOLVED' else 0
    cc=sorted(cases,key=lambda r:(families.index(r['family']),r['case_id']))
    z=np.array([[code(by[(r['case_id'],arm)]['result']) for r in cc] for arm in ['DIRECT_GUIDANCE','FRAMEWORK']])
    assert all(by[(r['case_id'],'DIRECT_GUIDANCE')]['result']==by[(r['case_id'],'FRAMEWORK')]['result'] for r in cc)
    fig=plt.figure(figsize=(7.2,8.25));gs=fig.add_gridspec(3,2,left=.23,right=.98,bottom=.10,top=.95,wspace=.78,hspace=.62,height_ratios=[.58,1,1])
    a=fig.add_subplot(gs[0,:]);b=fig.add_subplot(gs[1:,0]);c=fig.add_subplot(gs[1,1]);d=fig.add_subplot(gs[2,1])
    panel(a,'A','Same evidence, identical fair-arm decisions')
    cols=[BLUE,'#E8B866',GREY]
    matrix(a,z,cmap=ListedColormap(cols),vmin=0,vmax=2)
    start=0;centres=[]
    for fam in families:
        n=sum(r['family']==fam for r in cc);centres.append(start+(n-1)/2);start+=n;a.axvline(start-.5,color='white',lw=1.5)
    a.set(yticks=[0,1],yticklabels=['Direct guidance','Framework'],xticks=centres,xticklabels=['Reference\n19','Order\n3','Production\n15','Source\n11','New target\n19','Artificial\n23'])
    a.legend(handles=[Patch(facecolor=col,label=lab) for col,lab in zip(cols,['Determined / permitted','Unresolved','Held'])],loc='upper center',bbox_to_anchor=(.5,-.48),ncol=3,fontsize=8,columnspacing=1,handlelength=1)
    panel(b,'B','Artificial boundary geometry')
    artificial=[r for r in cases if r['family']=='artificial_boundaries']; valid=[];omitted=[]
    for r in artificial:
        try:lo,hi,t=float(r['lower']),float(r['upper']),float(r['threshold'])
        except (TypeError,ValueError):omitted.append(r);continue
        if not np.isfinite([lo,hi,t]).all() or lo>hi or not r['target_supported']:omitted.append(r);continue
        valid.append((r,lo-t,hi-t))
    assert (len(valid),len(omitted))==(18,5)
    # Dimensionless signed coordinates retain threshold geometry, not case units.
    for i,(r,lo,hi) in enumerate(valid):
        scale=max(abs(float(r['threshold'])),1); col=cols[code(r['expected'])]
        b.plot([lo/scale,hi/scale],[i,i],color=col,lw=1.5,marker='|',ms=5)
        if lo==hi:b.scatter(lo/scale,i,s=18,color=col)
    labels=[r['id'].replace('reference_','ref: ').replace('ratio_','ratio: ').replace('difference_','diff: ').replace('_',' ') for r,_,_ in valid]
    b.axvline(0,color=INK,lw=.7,ls='--');b.set(yticks=range(18),yticklabels=labels,ylim=(17.7,-.7),xscale='symlog',xlim=(-4,4),xlabel='(Endpoint − threshold) /\nmax(|threshold|, 1); symlog')
    b.set_xscale('symlog',linthresh=1e-10);b.set_xticks([-1,0,1],['−1','0','1'])
    fig.text(.60,.015,'B: 18 numeric fixtures shown; 4 invalid + 1 incompatible held',ha='center',fontsize=8)
    for ax,letter,metric,title in [(c,'C','unsupported_permission','Unsupported permissions'),(d,'D','unnecessary_withholding','Unnecessary holds')]:
        panel(ax,letter,title);arms=['NUMERIC_ONLY','ZERO_WIDTH_ONLY','IGNORE_TARGET']
        z=np.array([[int(next(r for r in fs if r['family']==fam and r['arm']==arm)[metric]) for arm in arms] for fam in families])
        matrix(ax,z,cmap='Oranges' if letter=='C' else 'Blues',vmin=0,vmax=23)
        for i,fam in enumerate(families):
            n=sum(r['family']==fam for r in cases)
            for j in range(3):ax.text(j,i,f'{z[i,j]}/{n}',ha='center',va='center',fontsize=8,color='white' if z[i,j]>13 else INK)
        ax.set(xticks=range(3),xticklabels=['No source\nqualifiers','Point\nonly','No target\ncheck'],yticks=range(6),yticklabels=flabels)
    save(fig,'figure_4_comparison','ABCD',
      'Finite same-evidence comparison, not measured assessor performance. (A) One column per case within six separate families; the two fair implementations give identical exact decisions. Colour groups decisions only for display. (B) Eighteen valid artificial intervals centred on their declared thresholds and scaled by max(|threshold|, 1), on a symmetric-log axis; four invalid and one target-incompatible fixtures are held and not assigned plotted intervals. Reference exceedance uses a strict > rule; an ordering interval touching equality is unresolved. (C–D) Unsupported permissions and unnecessary withholding under three deliberately incomplete implementations, with full family denominators in every cell. These controlled omissions are not usual-practice error rates. Cases are developer-derived, dependent and heterogeneous; they support neither pooled accuracy nor demonstrated superiority or independent human validation.',
      {'A':['comparator_v29/cases.json','comparator_v29/case_results.csv'],'B':['comparator_v29/cases.json'],'C':['comparator_v29/family_summary.csv'],'D':['comparator_v29/family_summary.csv']})
    assert all(sha(data/p)==h for p,h in inputs.items())
    (out/'audit.json').write_text(json.dumps({'inputs':inputs,'figures':figures,'new_exposure_calculations':0,'new_burden_calculations':0},indent=2))
    print(json.dumps({'out':str(out),'panels':sum(len(f['panels']) for f in figures)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path);p.add_argument('--out',required=True,type=Path);args=p.parse_args()
    if args.data is None:
        root=Path(__file__).resolve().parents[2];cfg=yaml.safe_load((root/'00_admin/paths.yaml').read_text())
        assert Path(cfg['data_root']).is_dir()
        args.data=root/'10_submission/最终投稿材料_v29_公平比较定稿_文件夹版/03_可复现数据与代码_NOT_DIRECT_UPLOAD'
    build(args.data,args.out)
