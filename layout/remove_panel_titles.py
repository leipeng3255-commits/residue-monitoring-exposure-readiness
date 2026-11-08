"""Remove relocated panel subtitles and compact SVGs; plotted values are unchanged."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse,hashlib,json,shutil,subprocess,os
from lxml import etree as E
from PIL import Image
NS='http://www.w3.org/2000/svg';N={'s':NS}
INK=os.environ.get('INKSCAPE',shutil.which('inkscape') or '/Applications/Inkscape.app/Contents/MacOS/inkscape')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(root,path):E.ElementTree(root).write(str(path),encoding='utf-8',xml_declaration=True)
def bounds(path):
 r=subprocess.run([INK,str(path),'--query-all'],check=True,capture_output=True,text=True)
 out={}
 for line in r.stdout.splitlines():
  parts=line.split(',')
  if len(parts)==5:
   try:out[parts[0]]=tuple(float(x)*.75 for x in parts[1:])
   except ValueError:pass
 return out
def shift(g,x,y):g.set('transform',f'translate({x:.6f},{y:.6f}) '+g.get('transform',''))
def grid(name,n):
 if '_S1_' in name:return 2,[(0,0,1,1),(0,1,1,1),(1,0,1,2)]
 if '_S2_' in name:return 1,[(0,0,1,1),(1,0,1,1)]
 if '_S3_' in name:return 2,[(0,0,1,2),(1,0,2,1),(1,1,1,1),(2,1,1,1)]
 if '_S4_' in name:return 6,[(0,0,1,6),(1,0,1,3),(1,3,1,3),(2,0,1,2),(2,2,1,2),(2,4,1,2)]
 return 2,[(i//2,i%2,1,1) for i in range(n)]
def main(src,out):
 out.mkdir(parents=True,exist_ok=False);receipts=[]
 for source in sorted(src.glob('*.svg')):
  root=E.parse(str(source)).getroot();original=deepcopy(root);removed=[]
  for g in root.xpath('//*[@id and starts-with(@id,"panel_caption_")]'):
   removed.extend(' '.join(''.join(t.itertext()).split()) for t in g.findall('.//s:text',N));g.getparent().remove(g)
  fig=root.find('.//s:g[@id="figure_1"]',N)
  bg=next((e for e in fig if e.tag=='{'+NS+'}rect' and e.get('fill')=='white'),None)
  assert bg is not None;fig.remove(bg)
  panels=sorted([(g.get('id')[-1],g) for g in fig if g.get('id','').startswith('panel_') and len(g.get('id',''))==7])
  assert panels
  dest=out/source.name;save(root,dest);b=bounds(dest);cols,cells=grid(source.stem,len(panels));gx=12;gy=14;margin=8
  cw=max((b[g.get('id')][2]-gx*(cs-1))/cs for (_,g),(_,_,_,cs) in zip(panels,cells));nr=max(r+rs for r,c,rs,cs in cells);heights=[0.0]*nr
  for (_,g),(r,c,rs,cs) in zip(panels,cells):
   if rs==1:heights[r]=max(heights[r],b[g.get('id')][3])
  for (_,g),(r,c,rs,cs) in zip(panels,cells):
   missing=b[g.get('id')][3]-(sum(heights[r:r+rs])+gy*(rs-1))
   if missing>0:
    for j in range(r,r+rs):heights[j]+=missing/rs
  width=2*margin+cols*cw+(cols-1)*gx;ids={id(g) for _,g in panels};extras=[g for g in fig if id(g) not in ids];top=margin;bottom_extras=[]
  for g in extras:
   if source.stem=='figure_S1_organic_identification' and g.get('id','').startswith('legend'):
    x,y,w,h=b[g.get('id')];shift(g,(width-w)/2-x,top-y);top+=h+12
   else:bottom_extras.append(g)
  for (letter,g),(r,c,rs,cs) in zip(panels,cells):
   x,y,w,h=b[g.get('id')];nx=margin+c*(cw+gx);ny=top+sum(heights[:r])+r*gy
   shift(g,nx-x,ny-y)
  bottom=top+sum(heights)+gy*(nr-1)
  for g in bottom_extras:
   x,y,w,h=b[g.get('id')];bottom+=12;shift(g,(width-w)/2-x,bottom-y);bottom+=h
  height=bottom+margin;root.set('width',f'{width:.6f}pt');root.set('height',f'{height:.6f}pt');root.set('viewBox',f'0 0 {width:.6f} {height:.6f}')
  bg.set('width',str(width));bg.set('height',str(height));fig.insert(0,bg);save(root,dest)
  def geometry(t):return Counter((e.tag,tuple(sorted(e.attrib.items()))) for e in t.iter() if isinstance(e.tag,str) and E.QName(e).localname in ['path','use','circle','ellipse','polyline','polygon','clipPath'])
  assert geometry(original)==geometry(root)
  def texts(t):return Counter(' '.join(''.join(e.itertext()).split()) for e in t.findall('.//s:text',N))
  assert texts(original)-Counter(removed)==texts(root)
  assert not root.xpath('//*[@id and starts-with(@id,"panel_caption_")]')
  assert len(root.xpath('//*[@id and starts-with(@id,"panel_letter_")]'))==len(panels)
  for label,g in panels:
   x,y,w,h=bounds(dest)[g.get('id')];assert x>=-.1 and y>=-.1 and x+w<=width+.1 and y+h<=height+.1,(source,label)
  subprocess.run([INK,str(dest),'--export-type=pdf','--export-filename='+str(dest.with_suffix('.pdf'))],check=True,capture_output=True)
  subprocess.run([INK,str(dest),'--export-type=png','--export-dpi=600','--export-background=white','--export-filename='+str(dest.with_suffix('.png'))],check=True,capture_output=True)
  Image.open(dest.with_suffix('.png')).convert('RGB').save(dest.with_suffix('.tiff'),compression='tiff_lzw',dpi=(600,600))
  receipts.append({'figure':source.stem,'panels':len(panels),'removed_subtitle_lines':removed,'source_sha256':sha(source),'svg_sha256':sha(dest),'plotted_geometry_unchanged':True,'other_text_unchanged':True})
  print(source.stem,len(panels),flush=True)
 assert len(receipts)==8 and sum(x['panels'] for x in receipts)==43
 (out/'panel_subtitle_removal_receipt.json').write_text(json.dumps(receipts,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();main(a.source,a.out)
