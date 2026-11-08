"""Reflow existing vector panels without changing any plotted data geometry.

Inkscape measures visible bounds. Panel titles move below their own panels,
letters enlarge, and panel groups translate into a compact grid. Source SVGs
remain untouched; no analysis is rerun.
"""
from pathlib import Path
from collections import Counter
from copy import deepcopy
from lxml import etree as E
from PIL import Image
import argparse, hashlib, json, re, subprocess, textwrap

NS='http://www.w3.org/2000/svg'; N={'s':NS}
INK='/Applications/Inkscape.app/Contents/MacOS/inkscape'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(root,path):E.ElementTree(root).write(str(path),encoding='utf-8',xml_declaration=True)
def bounds(path):
    out=subprocess.run([INK,str(path),'--query-all'],check=True,capture_output=True,text=True).stdout
    d={}
    for line in out.splitlines():
        v=line.split(',')
        if len(v)==5:
            try:d[v[0]]=tuple(float(x)*.75 for x in v[1:])
            except ValueError:pass
    return d
def shift(e,x,y):e.set('transform',f'translate({x:.6f},{y:.6f}) '+e.get('transform',''))
def textnode(x,y,s,size,anchor='start'):
    e=E.Element('{'+NS+'}text',x=str(x),y=str(y))
    e.set('style',f"font-family:'DejaVu Sans';font-weight:700;font-size:{size}px;text-anchor:{anchor}")
    e.text=s;return e
def grid(name,n):
    if '_S1_' in name:return 2,[(0,0,1,1),(0,1,1,1),(1,0,1,2)]
    if '_S2_' in name:return 1,[(0,0,1,1),(1,0,1,1)]
    if '_S3_' in name:return 2,[(0,0,1,2),(1,0,2,1),(1,1,1,1),(2,1,1,1)]
    if '_S4_' in name:return 6,[(0,0,1,6),(1,0,1,3),(1,3,1,3),(2,0,1,2),(2,2,1,2),(2,4,1,2)]
    return 2,[(i//2,i%2,1,1) for i in range(n)]
def build(src,out):
    out.mkdir(parents=True,exist_ok=True);receipts=[]
    for source in sorted(src.glob('*.svg')):
        root=E.parse(str(source)).getroot();before=deepcopy(root)
        fig=root.find('.//s:g[@id="figure_1"]',N);panels=[];titles={}
        for g in list(fig):
            hits=[]
            for t in g.findall('.//s:text',N):
                s=''.join(t.itertext());m=re.match(r'^([A-J])\s{1,}(.+)$',s)
                if m:hits.append((t,m))
            if hits:
                assert len(hits)==1,(source,hits)
                t,m=hits[0];letter,title=m.groups()
                size=float(re.search(r'font-size:\s*([\d.]+)',t.get('style')).group(1))
                titles[letter]=(title,size);t.getparent().remove(t)
                g.set('id','panel_'+letter);panels.append((letter,g))
        panels.sort();assert [p[0] for p in panels]==list('ABCDEFGHIJ'[:len(panels)])
        # The colour scale belongs to panel A, not to the canvas margin.
        if source.stem=='figure_3_disclosure':
            cbar=fig.find('s:g[@id="axes_1"]',N);fig.remove(cbar);panels[0][1].append(cbar)
        background=fig.find('s:g[@id="patch_1"]',N);fig.remove(background)
        if source.stem=='figure_S4_external_source_challenge':
            for t in root.findall('.//s:text',N):
                if (t.text or '').startswith('Denominators are intentionally incomparable:'):
                    words=t.text;t.text=None
                    for k,line in enumerate(textwrap.wrap(words,95,break_long_words=False,break_on_hyphens=False)):
                        span=E.SubElement(t,'{'+NS+'}tspan',x=t.get('x'),dy='0' if k==0 else '9')
                        span.text=line+' '
        dest=out/source.name;save(root,dest);b=bounds(dest)
        for letter,g in panels:
            x,y,w,h=b[g.get('id')];title,size=titles[letter]
            label=textnode(x,y-4,letter,max(14,size*1.55));label.set('id','panel_letter_'+letter);g.append(label)
            # Word wrapping affects only the display; original title words are retained.
            lines=textwrap.wrap(title,width=max(18,int(w/(size*.54))),break_long_words=False,break_on_hyphens=False)
            title_group=E.SubElement(g,'{'+NS+'}g',id='panel_caption_'+letter)
            for k,line in enumerate(lines):title_group.append(textnode(x+w/2,y+h+size+4+k*size*1.22,line,size,'middle'))
        save(root,dest);b=bounds(dest)
        cols,cells=grid(source.stem,len(panels));gap_x=12;gap_y=9;margin=8
        col_width=max((b[g.get('id')][2]-gap_x*(cs-1))/cs for (_,g),(_,_,_,cs) in zip(panels,cells))
        nr=max(r+rs for r,c,rs,cs in cells);heights=[0.0]*nr
        for (_,g),(r,c,rs,cs) in zip(panels,cells):
            if rs==1:heights[r]=max(heights[r],b[g.get('id')][3])
        for (_,g),(r,c,rs,cs) in zip(panels,cells):
            deficit=b[g.get('id')][3]-(sum(heights[r:r+rs])+gap_y*(rs-1))
            if deficit>0:
                for j in range(r,r+rs):heights[j]+=deficit/rs
        width=2*margin+cols*col_width+(cols-1)*gap_x
        panel_nodes={id(g) for _,g in panels}
        extras=[g for g in fig if id(g) not in panel_nodes]
        # The production-label legend is shared by A/B and stays above those panels.
        top=margin;bottom_extras=[]
        for g in extras:
            if source.stem=='figure_S1_organic_identification' and g.get('id','').startswith('legend'):
                x,y,w,h=b[g.get('id')];shift(g,(width-w)/2-x,top-y);top+=h+12
            else:bottom_extras.append(g)
        positions=[]
        for (letter,g),(r,c,rs,cs) in zip(panels,cells):
            x,y,w,h=b[g.get('id')];cell_w=cs*col_width+(cs-1)*gap_x
            nx=margin+c*(col_width+gap_x)+(cell_w-w)/2;ny=top+sum(heights[:r])+gap_y*r
            shift(g,nx-x,ny-y)
            g.find('./s:text[@id="panel_letter_'+letter+'"]',N).set('x',str(margin+c*(col_width+gap_x)-(nx-x)))
            positions.append(dict(panel=letter,x=nx,y=ny,width=w,height=h))
        bottom=top+sum(heights)+gap_y*(nr-1)
        for g in bottom_extras:
            x,y,w,h=b[g.get('id')];bottom+=12;shift(g,(width-w)/2-x,bottom-y);bottom+=h
        height=bottom+margin
        root.set('width',f'{width:.6f}pt');root.set('height',f'{height:.6f}pt');root.set('viewBox',f'0 0 {width:.6f} {height:.6f}')
        rect=E.Element('{'+NS+'}rect',x='0',y='0',width=str(width),height=str(height),fill='white')
        fig.insert(0,rect);save(root,dest)
        # Scientific paths, marker uses, axis transforms, styles and text remain unchanged.
        before_fig=before.find('.//s:g[@id="figure_1"]',N)
        before_fig.remove(before_fig.find('s:g[@id="patch_1"]',N))
        def geometry(tree):
            return Counter((e.tag,tuple(sorted(e.attrib.items()))) for e in tree.iter() if isinstance(e.tag,str) and E.QName(e).localname in ['path','use','polygon','polyline','circle','ellipse','clipPath'])
        assert geometry(before)==geometry(root),(source,'geometry changed')
        def texts(tree):return Counter(' '.join(''.join(e.itertext()).split()) for e in tree.findall('.//s:text',N))
        expected=texts(before)
        for letter,(title,_) in titles.items():
            expected[letter+' '+title]-=1
            if not expected[letter+' '+title]:del expected[letter+' '+title]
        actual=texts(root)
        for letter,g in panels:
            actual[letter]-=1
            for t in g.findall('./s:g[@id="panel_caption_'+letter+'"]//s:text',N):actual[' '.join(t.text.split())]-=1
        assert +actual==+expected,(source,'non-title text changed')
        final=bounds(dest)
        for letter,_ in panels:
            x,y,w,h=final['panel_'+letter];assert x>=-0.1 and y>=-0.1 and x+w<=width+.1 and y+h<=height+.1
        subprocess.run([INK,str(dest),'--export-type=pdf','--export-filename='+str(dest.with_suffix('.pdf'))],check=True,capture_output=True)
        subprocess.run([INK,str(dest),'--export-type=png','--export-dpi=600','--export-background=white','--export-filename='+str(dest.with_suffix('.png'))],check=True,capture_output=True)
        im=Image.open(dest.with_suffix('.png')).convert('RGB');im.save(dest.with_suffix('.tiff'),compression='tiff_lzw',dpi=(600,600))
        receipts.append(dict(figure=source.stem,panels=len(panels),source_sha256=sha(source),svg_sha256=sha(dest),all_data_geometry_unchanged=True,non_title_text_unchanged=True,positions=positions,original_viewbox=before.get('viewBox'),new_viewbox=root.get('viewBox')))
        print(source.stem,len(panels),'panels',flush=True)
    (out/'layout_receipt.json').write_text(json.dumps(receipts,indent=2)+'\n')
    assert sum(r['panels'] for r in receipts)==43
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.source,a.out)
