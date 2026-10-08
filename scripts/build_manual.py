"""Build the manual PDF, clickable TOC and bookmarks from the Markdown source."""
from pathlib import Path
import argparse,re,html,json
from PIL import Image as PILImage, ImageDraw
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import pypdfium2 as pdfium
from manual_figures import generate

ROOT=Path(__file__).resolve().parents[1]; DOC=ROOT/'docs'; TMP=ROOT/'tmp/manual-v21-public'; ASSETS=DOC/'assets/manual'; OUT=ROOT/'output/pdf'
for p in [TMP,ASSETS,OUT]:p.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser(); ap.add_argument('--cad-dir',type=Path); ap.add_argument('--skip-cad',action='store_true'); ap.add_argument('--github-account',default='J-ShuJie'); ap.add_argument('--author',default=''); ap.add_argument('--language',choices=['zh','en','de'],default='zh'); args=ap.parse_args()
LANG={'zh':('制作与使用手册','中文','目录','版本 1.0  /  中文','GitHub账号：','作者：'),'en':('Assembly and User Manual','English','Contents','Version 1.0  /  English','GitHub: ','Author: '),'de':('Bau- und Bedienungsanleitung','Deutsch','Inhalt','Version 1.0  /  Deutsch','GitHub: ','Autor: ')}[args.language]
TMP=ROOT/('tmp/manual-v21-public' if args.language=='zh' else 'tmp/manual-'+args.language);TMP.mkdir(parents=True,exist_ok=True)
if not args.skip_cad:
    if not args.cad_dir:ap.error('--cad-dir required')
    generate(args.cad_dir,TMP,ASSETS)
pdfmetrics.registerFont(TTFont('Manual','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('ManualBold','C:/Windows/Fonts/msyhbd.ttc',subfontIndex=0))
pdfmetrics.registerFontFamily('Manual',normal='Manual',bold='ManualBold')
S={}
for key,size,lead,color in [('p',10,16,'#293b43'),('h1',35,44,'#174e55'),('h2',18,26,'#174e55'),('h3',12,20,'#174e55'),('cell',9,14,'#293b43'),('caption',8.5,13,'#60777b'),('note',9,15,'#875319')]:
    S[key]=ParagraphStyle(key,fontName='ManualBold' if key.startswith('h') else 'Manual',fontSize=size,leading=lead,wordWrap='CJK' if args.language=='zh' else None,spaceAfter=8,textColor=color,keepWithNext=key in ['h2','h3'])
if args.language!='zh':
    for key,size,lead in [('p',9.5,14.5),('cell',8.5,12.5)]:
        S[key].fontSize=size;S[key].leading=lead
S['h2'].spaceBefore=14
S['h2'].spaceAfter=10
S['h3'].spaceBefore=12
S['h3'].spaceAfter=7
S['caption'].spaceBefore=5
S['caption'].spaceAfter=10
S['list']=ParagraphStyle('list',parent=S['p'],leftIndent=17,firstLineIndent=-17,spaceAfter=5)
S['meta']=ParagraphStyle('meta',parent=S['p'],fontSize=9,leading=15,textColor='#60777b',spaceAfter=3)
S['headcell']=ParagraphStyle('headcell',parent=S['cell'],fontName='ManualBold',textColor='#174e55')

def inline(s):
    s=s.replace('**','').replace('`','').replace('🟠 ','')
    result=[]; pos=0
    for m in re.finditer(r'\[([^]]+)\]\((https?://[^)]+)\)',s):
        result.append(html.escape(s[pos:m.start()]))
        result.append('<link href="'+html.escape(m[2],quote=True)+'" color="#166e78">'+html.escape(m[1])+'</link>')
        pos=m.end()
    result.append(html.escape(s[pos:]))
    return ''.join(result)

def note(s):
    t=Table([[Paragraph(inline(s),S['note'])]],colWidths=[499])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),'#fff4dd'),('BOX',(0,0),(-1,-1),.6,'#d4a04b'),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),11)]))
    return [t,Spacer(1,10)]
class ManualDoc(BaseDocTemplate):
    def __init__(self,path):
        super().__init__(str(path),pagesize=(595,842),leftMargin=48,rightMargin=48,topMargin=42,bottomMargin=46,title='PetriTrace '+LANG[0],author=args.author or args.github_account)
        self.addPageTemplates(PageTemplate('normal',Frame(48,48,499,736,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0),onPage=self.footer))
        self.heading_pages=[]
    def beforeDocument(self):
        self.previous_heading_pages=self.heading_pages[:]
        self.heading_pages=[]
        self.current_chapter=LANG[2]
    def footer(self,c,d):
        if d.page==1:return
        c.saveState()
        c.setStrokeColor(colors.HexColor('#d6e4e3'));c.setLineWidth(.5)
        c.line(48,38,547,38)
        c.setFont('Manual',7.5);c.setFillColor(colors.HexColor('#60777b'))
        chapter_opening=any(h.get('level')==0 and h['page']==d.page for h in self.previous_heading_pages)
        if not chapter_opening:
            c.line(48,803,547,803)
            c.drawString(48,812,'PetriTrace')
            chapters=[h['title'] for h in self.previous_heading_pages if h.get('level')==0 and h['page']<=d.page]
            c.drawRightString(547,812,chapters[-1] if chapters else self.current_chapter)
        c.drawString(48,24,LANG[0]+'  ·  '+LANG[1])
        c.setFont('ManualBold',9);c.setFillColor(colors.HexColor('#174e55'));c.drawRightString(547,24,f'{d.page:02}')
        c.restoreState()
    def afterFlowable(self,f):
        if hasattr(f,'anchor'):
            if f.level==0:self.current_chapter=f.getPlainText()
            self.canv.bookmarkPage(f.anchor)
            self.canv.addOutlineEntry(f.getPlainText(),f.anchor,f.level,False)
            self.notify('TOCEntry',(f.level,f.getPlainText(),self.page,f.anchor))
            self.heading_pages.append({'title':f.getPlainText(),'page':self.page,'anchor':f.anchor,'level':f.level})

# Trim only white margins for the cover; preserve the photo and its shadow.
cover=PILImage.open(ASSETS/'photos/cover-front.png').convert('RGB')
cover=cover.crop((270,245,1867,2108))
cover_path=TMP/'cover-layout.png'; cover.save(cover_path)
cw,ch=cover.size; cs=min(470/cw,485/ch)
story=[Spacer(1,8),Paragraph('PetriTrace',S['h1']),Paragraph(LANG[0],S['h2']),Spacer(1,14),Image(str(cover_path),width=cw*cs,height=ch*cs),Spacer(1,16),Paragraph(LANG[3],S['meta'])]
if args.author:story.append(Paragraph(LANG[5]+html.escape(args.author),S['meta']))
if args.github_account:story.append(Paragraph(LANG[4]+html.escape(args.github_account),S['meta']))
story.append(Paragraph(inline('[https://github.com/J-ShuJie/PetriTrace](https://github.com/J-ShuJie/PetriTrace)'),S['meta']))
story += [PageBreak(),Paragraph(LANG[2],S['h2'])]
toc=TableOfContents(tableStyle=TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]));toc.levelStyles=[ParagraphStyle('toc0',fontName='Manual',fontSize=11,leading=20,spaceBefore=6,textColor='#174e55'),ParagraphStyle('toc1',fontName='Manual',fontSize=9,leading=16,leftIndent=16)]
story += [toc,PageBreak()]
lines=(DOC/('PetriTrace制作与使用手册.md' if args.language=='zh' else 'PetriTrace_Manual_'+args.language+'.md')).read_text(encoding='utf-8').splitlines()
i=next(i for i,l in enumerate(lines) if l.startswith('## 1.'))
while i<len(lines):
    line=lines[i].strip();i+=1
    if not line or line.startswith('<a '):continue
    if re.match(r'(?:表 \d+　|(?:Table|Tabelle) \d+\.)',line):
        cap=Paragraph(inline(line),S['caption']);cap.keepWithNext=True;story.append(cap);continue
    if line.startswith('> '):story+=note(line[2:]);continue
    if line.startswith('|'):
        rows=[line]
        while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
        rows=[r for r in rows if not re.fullmatch(r'[| :\-]+',r)]
        data=[[Paragraph(inline(c.strip()),S['headcell'] if row_index==0 else S['cell']) for c in r.strip('|').split('|')] for row_index,r in enumerate(rows)]
        n=len(data[0]);widths=[125,374] if n==2 else [110,45,344]
        if any(t in rows[0] for t in ['起点','| From |','| Von |']):widths=[130,170,199]
        if any(t in rows[0] for t in ['安装位置','Mounting location','Einbauort']):widths=[180,200,119]
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('ROWBACKGROUNDS',(0,1),(-1,-1),['#ffffff','#f4f8f7']),('BACKGROUND',(0,0),(-1,0),'#deedeb'),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,'#94b9b5'),('LINEBELOW',(0,-1),(-1,-1),.5,'#c7d8d7'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.extend([t,Spacer(1,10)]);continue
    m=re.match(r'!\[(.*?)\]\((.*?)\)',line)
    if m:
        # Pair the introductory photo and CAD overview for direct comparison.
        if m[2]=='assets/manual/photos/front.jpg':
            following=i
            while following<len(lines) and not lines[following].strip():following+=1
            second=re.match(r'!\[(.*?)\]\((.*?)\)',lines[following].strip())
            if second and second[2]=='assets/manual/assembly.png':
                pictures=[];captions=[]
                for entry in [m,second]:
                    picture=DOC/entry[2];pw,ph=PILImage.open(picture).size;ratio=min(232/pw,200/ph)
                    pictures.append(Image(str(picture),width=pw*ratio,height=ph*ratio))
                    captions.append(Paragraph(inline(entry[1]),S['caption']))
                pair=Table([pictures,captions],colWidths=[249.5,249.5],hAlign='LEFT')
                pair.setStyle(TableStyle([('VALIGN',(0,0),(-1,0),'MIDDLE'),('VALIGN',(0,1),(-1,1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
                story.append(KeepTogether([pair,Spacer(1,5)]));i=following+1;continue
        path=DOC/m[2];w,h=PILImage.open(path).size;scale=min((440 if path.parent.name=='ui' else 480)/w,(205 if path.stem=='front' else 185 if path.stem=='assembly' else 340 if path.stem=='interior' else 400 if path.parent.name=='ui' else 520 if path.stem=='parts' else 470 if path.stem=='exploded' else 380 if path.stem=='door' else 300)/h)
        story.append(KeepTogether([Image(str(path),width=w*scale,height=h*scale),Paragraph(inline(m[1]),S['caption'])]));continue
    m=re.match(r'(#{2,3}) (.+)',line)
    if m:
        level=len(m[1])-2
        if level==0 and not isinstance(story[-1],PageBreak):story.append(PageBreak())
        p=Paragraph(inline(m[2]),S['h'+str(level+2)]);p.anchor='section-'+m[2].split(' ')[0].rstrip('.').replace('.','-');p.level=level;story.append(p);continue
    story.append(Paragraph(inline(line),S['list'] if re.match(r'^\d+\. ',line) else S['p']))

for j in range(len(story)-2,-1,-1):
    if hasattr(story[j],'anchor') and isinstance(story[j+1],KeepTogether):
        story[j:j+2]=[KeepTogether([story[j],*story[j+1]._content])]
out=OUT/('PetriTrace制作与使用手册_第21版_打印.pdf' if args.author else 'PetriTrace制作与使用手册_第21版_GitHub.pdf')
if args.language!='zh':out=OUT/('PetriTrace_Manual_'+args.language+'.pdf')
doc=ManualDoc(out); doc.multiBuild(story)
(TMP/'headings.json').write_text(json.dumps(doc.heading_pages,ensure_ascii=False,indent=2),encoding='utf-8')
pdf=pdfium.PdfDocument(str(out));thumbs=[]
for n in range(len(pdf)):
    im=pdf[n].render(scale=1.2).to_pil().convert('RGB');im.save(TMP/f'page-{n+1:02}.png');im.thumbnail((298,421));thumbs.append(im)
contact=PILImage.new('RGB',(1192,445*((len(thumbs)+3)//4)),'#dce5e5');d=ImageDraw.Draw(contact)
for n,im in enumerate(thumbs):x=n%4*298;y=n//4*445;contact.paste(im,(x,y));d.text((x+8,y+423),str(n+1),fill='black')
contact.save(TMP/'contact.png');print('PDF pages:',len(pdf))
