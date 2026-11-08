"""Two source-driven, editable v31 figures. No exposure is recalculated."""
import argparse,csv,json,hashlib,collections as C
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import yaml
BLUE,ORANGE,TEAL,GREY,INK='#0072B2','#D55E00','#009E73','#B9C1C9','#28343D'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
 'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,
 'legend.frameon':False,'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'v31',
 'savefig.facecolor':'white'})
def panel(ax,l,t):ax.set_gid('panel_'+l);ax.set_title(l+'  '+t,loc='left',fontweight='bold',pad=11)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(data,out):
 out.mkdir(parents=True,exist_ok=False);inputs={};figures=[]
 def read(p):
  inputs[p]=sha(data/p);return list(csv.DictReader((data/p).open()))
 def ext(name):return read('depth_extension_v31/'+name+'.csv')
 def save(fig,stem,caption,sources):
  fig.canvas.draw();renderer=fig.canvas.get_renderer();bad=[]
  ticks={id(t) for ax in fig.axes for t in ax.get_xticklabels()+ax.get_yticklabels()}
  for text in fig.findobj(matplotlib.text.Text):
   if not text.get_visible() or not text.get_text() or id(text) in ticks:continue
   b=text.get_window_extent(renderer)
   if b.x0 < -1 or b.y0 < -1 or b.x1>fig.bbox.x1+1 or b.y1>fig.bbox.y1+1:bad.append(text.get_text())
  assert not bad,(stem,bad)
  for extension in ['svg','pdf','png','tiff']:
   fig.savefig(out/(stem+'.'+extension),dpi=600,**({'pil_kwargs':{'compression':'tiff_lzw'}} if extension=='tiff' else {}))
  svg=(out/(stem+'.svg')).read_text();assert '<image' not in svg and '<text' in svg
  figures.append(dict(stem=stem,panels=list('ABCDEF'),caption=caption,source_by_panel=sources,physical_inches=list(fig.get_size_inches()),text_outside_canvas=bad))
  plt.close(fig)
 ad=read('tables/admission_decision_ledger.csv');st=read('tables/strict_37_ledger.csv')
 inv=ext('all_declared_code_inventory');gates=ext('concurrent_gate_262_long');bundles=ext('necessary_evidence_bundles')
 assert len(ad)==262 and len(st)==37 and len(inv)==1392
 fig,axs=plt.subplots(3,2,figsize=(7.2,9.2));fig.subplots_adjust(left=.20,right=.97,top=.955,bottom=.15,wspace=.85,hspace=.84)
 a,b,c,d,e,f=axs.ravel()
 panel(a,'A','Scope precedes admission')
 vals=[180,45,18,19];labels=['Outside fixed target','Below study rule','Chemistry held','Admitted']
 for i,(n,col) in enumerate(zip(vals,[GREY,'#E8B866',ORANGE,BLUE])):
  a.barh(i,n,color=col,height=.5);a.text(n+3,i,str(n),va='center')
 a.set(yticks=range(4),yticklabels=labels,ylim=(3.7,-.6),xlim=(0,207),xlabel='Historical candidate keys (262)')
 panel(b,'B','Strict-set chemistry')
 vals=[18,1,10,8]
 b.barh(range(4),vals,color=[BLUE,TEAL,ORANGE,GREY],height=.5)
 for i,n in enumerate(vals):b.text(n+.35,i,str(n),va='center')
 b.set(yticks=range(4),yticklabels=['Exact','Converted','Mismatch','Unresolved'],ylim=(3.7,-.6),xlim=(0,21),xlabel='Strict units (37)')
 panel(c,'C','All reported code units')
 for i,m in enumerate(['CZ','DE']):
  rs=[r for r in inv if r['market']==m];n0=sum(r['state']=='ALL_REPORTED_BELOW_LIMIT' for r in rs);n1=len(rs)-n0
  c.barh(i,n0,color=GREY,height=.5);c.barh(i,n1,left=n0,color=BLUE,height=.5)
  c.text(n0/2,i,str(n0),ha='center',va='center');c.text(len(rs)+20,i,str(n1),va='center',color=BLUE)
 c.set(yticks=[0,1],yticklabels=['CZ','DE'],ylim=(1.6,-.65),xlim=(0,1050),xlabel='Code × type × market units')
 c.legend(handles=[Patch(facecolor=GREY,label='All below limits'),Patch(facecolor=BLUE,label='Has VAL')],loc='upper center',bbox_to_anchor=(.45,-.33),ncol=1,fontsize=8)
 panel(d,'D','Declared expression types')
 types=['P005A','P002A','P004A','N_A'];colours=[BLUE,ORANGE,TEAL,GREY];left=np.zeros(2)
 for typ,col in zip(types,colours):
  ns=np.array([sum(r['market']==m and r['parameter_type']==typ for r in inv) for m in ['CZ','DE']]);d.barh([0,1],ns,left=left,color=col,height=.5,label=typ);left+=ns
 d.set(yticks=[0,1],yticklabels=['CZ','DE'],ylim=(1.6,-.65),xlim=(0,1000),xlabel='Reported units; not risk identities')
 d.legend(loc='upper center',bbox_to_anchor=(.42,-.33),ncol=2,fontsize=8,columnspacing=.8,handlelength=1)
 panel(e,'E','Concurrent requirements')
 inscope={r['unit_id'] for r in bundles if r['historical_target_in_scope']=='True'}
 names=['typed_numeric_limits','crop_specific_documentary_chemistry','source_identity_expression','raw_food_form','native_paired_output']
 labels=['Typed limits','Chemical basis','Source identity','Food form','Paired output'];left=np.zeros(5)
 for status,col,lab in [('VERIFIED',BLUE,'Documented'),('KNOWN_INCOMPATIBLE',ORANGE,'Incompatible'),('NOT_YET_AUDITED',GREY,'Not yet verified')]:
  ns=np.array([sum(r['gate']==g and r['status']==status and r['unit_id'] in inscope for r in gates) for g in names]);e.barh(range(5),ns,left=left,color=col,height=.57)
  for i,n in enumerate(ns):
   if n>=8:e.text(left[i]+n/2,i,str(n),ha='center',va='center',color='white' if col in (BLUE,ORANGE) else INK,fontsize=8)
  left+=ns
 assert list(left)==[82]*5
 e.set(yticks=range(5),yticklabels=labels,ylim=(4.7,-.6),xlim=(0,82),xticks=[0,40,82],xlabel='In-target historical keys (82)')
 panel(f,'F','No detection-count filter')
 for typ,col in zip(types,colours):
  points=C.Counter((int(r['samples']),100*int(r['quantified_records'])/int(r['rows'])) for r in inv if r['parameter_type']==typ)
  f.scatter([v[0] for v in points],[v[1] for v in points],s=[7+5*np.sqrt(n) for n in points.values()],color=col,alpha=.65,edgecolors='white',lw=.25)
 f.set(xlabel='Tested samples per reported unit',ylabel='VAL records (%)',xlim=(0,230),ylim=(-5,105),xticks=[0,100,200])
 fig.legend(handles=[Patch(facecolor=BLUE,label='Documented for stated gate (E)'),Patch(facecolor=ORANGE,label='Known incompatibility (E)'),Patch(facecolor=GREY,label='Review incomplete (E)')],loc='lower center',bbox_to_anchor=(.54,.008),ncol=1,fontsize=8)
 save(fig,'figure_1_qualification',
  'Qualification depends on scope, expression and review state. (A) Concurrent re-audit partitions 262 historical keys into 180 outside the fixed 2022 MACP tomato target in the checked frame, 45 in-target keys below the historical support rule, 18 strict chemistry holds and 19 admitted inputs. Outside-target is not absent surveillance. (B) Definition states among 37 strict candidates. (C) Threshold-unrestricted inventory: 490 CZ and 902 DE code–parameter-type units; 452/836 are all below limits and 38/66 have VAL records. These 1,392 units are not distinct risk-assessment chemicals. (D) Declared parameter-type composition; P005A, P002A, P004A and N_A are retained as source codes, not interchangeable identities. (E) Concurrent evidence states for 82 in-target historical keys. A recorded limit does not validate chemistry; incomplete review is not source nondisclosure. (F) All 1,392 reported units, without a quantified-count filter; marker area increases with coincident-unit count. Types follow D. All-code and historical frames are distinct; neither estimates national readiness.',
  {'A':['depth_extension_v31/necessary_evidence_bundles.csv','tables/strict_37_ledger.csv'],
   'B':['tables/strict_37_ledger.csv'],'C':['depth_extension_v31/all_declared_code_inventory.csv'],
   'D':['depth_extension_v31/all_declared_code_inventory.csv'],'E':['depth_extension_v31/concurrent_gate_262_long.csv','depth_extension_v31/necessary_evidence_bundles.csv'],
   'F':['depth_extension_v31/all_declared_code_inventory.csv']})
 cells=read('tables/cell_diagnostics.csv');surveys=read('tables/dietary_strata.csv');infl=ext('all19_influence_summary');rr=ext('shared_ratio_deletions');meta=ext('shared_sample_metadata')
 fig=plt.figure(figsize=(7.2,10.7));gs=fig.add_gridspec(4,2,left=.24,right=.975,top=.955,bottom=.07,wspace=.78,hspace=.9,height_ratios=[1.1,1.1,1,1])
 a=fig.add_subplot(gs[:2,0]);b=fig.add_subplot(gs[:2,1]);c=fig.add_subplot(gs[2,0]);d=fig.add_subplot(gs[2,1]);e=fig.add_subplot(gs[3,0]);f=fig.add_subplot(gs[3,1])
 panel(a,'A','Saved single-food results')
 ds=sorted(cells,key=lambda r:float(r['max_mean_percent_ADI_UB']),reverse=True)
 for i,r in enumerate(ds):a.plot([float(r['max_mean_percent_ADI_LB']),float(r['max_mean_percent_ADI_UB'])],[i,i],color=BLUE,lw=1.2)
 a.scatter([float(r['max_mean_percent_ADI_UB']) for r in ds],range(19),s=14,color=BLUE,label='Mean UB')
 a.scatter([float(r['max_native_HRP_percent_ADI_UB']) for r in ds],range(19),s=18,facecolor='white',edgecolor=INK,marker='D',label='Native HRP UB')
 a.set(yticks=range(19),yticklabels=[r['occurrence_country']+' '+r['pesticide'] for r in ds],ylim=(18.7,-.8),xscale='log',xlabel='ADI (%) · log scale',xticks=[.0001,.01,1],xticklabels=['0.0001','0.01','1'])
 a.legend(loc='upper left',bbox_to_anchor=(-.13,-.10),ncol=2,fontsize=8,handlelength=1,columnspacing=.5);a.grid(axis='x',color='#E6E9EC',lw=.5)
 panel(b,'B','Ordering and influence')
 chemicals=['azoxystrobin','boscalid','pyriproxyfen']
 for i,name in enumerate(chemicals):
  rs=[r for r in rr if r['pesticide']==name];y=i*3
  vals=[(float(rs[0]['original_lower']),float(rs[0]['original_upper']),INK,'o')]
  for market,col in [('CZ',ORANGE),('DE',BLUE)]:
   ss=[r for r in rs if r['omitted_market']==market];vals.append((min(float(r['lower']) for r in ss),max(float(r['upper']) for r in ss),col,'|'))
  for j,(lo,hi,col,marker) in enumerate(vals):b.plot([lo,hi],[y+j*.55,y+j*.55],color=col,lw=1.2,marker=marker,ms=4)
 b.axvline(1,color=GREY,lw=.9,ls='--');b.set(yticks=[.55,3.55,6.55],yticklabels=chemicals,ylim=(8,-.7),xscale='log',xlim=(min(float(r['lower']) for r in rr)*.8,22),xticks=[.1,1,5,20],xticklabels=['0.1','1','5','20'],xlabel='CZ / DE sampled mean')
 b.legend(handles=[plt.Line2D([],[],color=k,label=v) for k,v in [(INK,'Original bounds'),(ORANGE,'Omit CZ: envelope'),(BLUE,'Omit DE: envelope')]],loc='upper left',bbox_to_anchor=(-.05,-.1),fontsize=8,handlelength=1.2)
 panel(c,'C','Censoring and concentration')
 panel(d,'D','Single-lot mean influence')
 for market,col,marker in [('CZ',ORANGE,'o'),('DE',BLUE,'s')]:
  ss=[r for r in infl if r['market']==market]
  c.scatter([100*float(r['censor_width_fraction']) for r in ss],[100*float(r['largest_quantified_share']) for r in ss],s=27,color=col,marker=marker,edgecolor='white',lw=.4,label=market)
  d.scatter([100*(1-float(r['deletion_lower_min'])/float(r['lower'])) for r in ss],[100*(1-float(r['deletion_upper_min'])/float(r['upper'])) for r in ss],s=27,color=col,marker=marker,edgecolor='white',lw=.4)
 c.set(xlabel='(U − L) / U (%)',ylabel='Largest value / quantified sum (%)',xlim=(-2,103),ylim=(0,100));c.legend(loc='lower left',fontsize=8)
 d.plot([0,100],[0,100],ls='--',color=GREY,lw=.6);d.set(xlabel='Lower mean decrease (%)',ylabel='Upper mean decrease (%)',xlim=(0,100),ylim=(0,100))
 panel(e,'E','Different sampling calendars')
 for market,col,offset in [('CZ',ORANGE,-.18),('DE',BLUE,.18)]:
  totals={month:sum(int(r[market]) for r in meta if r['month']==str(month)) for month in range(1,13)};n=sum(totals.values())
  e.bar(np.arange(1,13)+offset,[100*totals[k]/n for k in range(1,13)],width=.34,color=col,label=f'{market} (n={n})')
 e.set(xlabel='Sampling month, 2022',ylabel='Samples (%)',xticks=[1,3,6,9,12],ylim=(0,55));e.legend(loc='upper right',fontsize=8)
 panel(f,'F','Dietary-survey age')
 gaps=C.Counter(int(float(r['survey_gap_to_monitoring_years'])) for r in surveys);f.bar(sorted(gaps),[gaps[k] for k in sorted(gaps)],color=BLUE,width=.7)
 f.set(xlabel='2022 − survey end year',ylabel='Dietary strata (88)',xticks=[10,14,18,22])
 save(fig,'figure_2_primo',
  'Calculability, censoring bounds and sample influence answer different questions. (A) Saved 19-input PRIMo contributions: mean LB–UB segments, mean UB circles and native high-percentile UB diamonds. Displayed maxima occur in Bulgaria/NUTRICHILD toddlers; the native maximum is P97.5. (B) Original ratio bounds and envelopes across all single-CZ-lot or single-DE-lot omissions for three shared chemicals (18/214 samples). An envelope joins the lowest lower and highest upper endpoint across different changed sets; it is neither one attainable interval nor a confidence interval. One CZ omission reverses boscalid ordering, and one makes pyriproxyfen unresolved; original observations remain in the primary result. (C) Censoring-width fraction and the largest quantified-value share for every admitted input. (D) Maximum lower/upper mean decreases across single-lot deletions, relative to each original endpoint, for all 19 inputs; symbols follow C. These changes describe reduced finite sets, not measurement errors or sampling probabilities. (E) Month distributions for the shared-chemical lots. Eight common month–origin categories contain 13/18 CZ and 32/214 DE lots; this is descriptive overlap, not matching. (F) Timing of 88 strata sharing 33 surveys. No national/current-population, total-diet-safety or common disease-risk inference is made.',
  {'A':['tables/cell_diagnostics.csv'],'B':['depth_extension_v31/shared_ratio_deletions.csv'],
   'C':['depth_extension_v31/all19_influence_summary.csv'],'D':['depth_extension_v31/all19_influence_summary.csv'],
   'E':['depth_extension_v31/shared_sample_metadata.csv'],'F':['tables/dietary_strata.csv']})
 assert all(sha(data/p)==h for p,h in inputs.items())
 (out/'audit.json').write_text(json.dumps(dict(inputs=inputs,figures=figures,new_exposure_calculations=0),indent=2))
 print(json.dumps({'out':str(out),'panels':12}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();build(a.data,a.out)
