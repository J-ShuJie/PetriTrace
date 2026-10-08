from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import textwrap
root=Path.cwd();src=root/'docs/assets/manual'
fontpath='C:/Windows/Fonts/segoeui.ttf'
def font(n):return ImageFont.truetype(fontpath,n)
def text(d,pos,s,n=25,width=None):
 f=font(n)
 while width and d.textlength(s,font=f)>width and n>14:n-=1;f=font(n)
 d.text(pos,s,font=f,fill='#173f45')
parts={
'en':['Left side','Hinge side','Bottom','Top','Centre divider','Shaped front','Lower camera panel','Upper frame','Screen layer 1','Screen layer 2','Screen layer 3','Screen layer 4','Screen layer 5','Door','Handle upright','Handle return','Door magnet','Body magnet front','Body magnet backing'],
'de':['Linke Seite','Scharnierseite','Boden','Deckel','Trennwand','Geformte Front','Untere Kameraplatte','Oberer Rahmen','Bildschirmlage 1','Bildschirmlage 2','Bildschirmlage 3','Bildschirmlage 4','Bildschirmlage 5','Tür','Griffsteg','Griffleiste','Türmagnet','Gehäusemagnet vorn','Gehäusemagnet hinten']}
for lang in ['en','de']:
 out=src/lang;out.mkdir(exist_ok=True)
 im=Image.open(src/'parts.png').convert('RGB');d=ImageDraw.Draw(im)
 for i,label in enumerate(parts[lang]):
  x=i%4*375;y=i//4*360;d.rectangle((x,y,x+374,y+39),fill='white');text(d,(x+18,y+6),f'{i+1:02} '+label,25,340)
 im.save(out/'parts.png')
 for name in ['handle','door-magnet','body-magnet','hinge-mount']:
  im=Image.open(src/(name+'.png')).convert('RGB');d=ImageDraw.Draw(im);d.rectangle((0,0,1799,90),fill='white')
  for i,label in enumerate(['Exploded alignment','Assembly position'] if lang=='en' else ['Teile und Ausrichtung','Einbauposition']):text(d,(i*900+35,25),label,34)
  im.save(out/(name+'.png'))
 # Reuse the unchanged geometry, replacing only the label regions.
 im=Image.open(src/'orientation.png').convert('RGB');d=ImageDraw.Draw(im)
 labels=[((35,25),(1490,65),'Installation orientation · schematic, not to scale','Einbaurichtung · schematisch, nicht maßstäblich'),((500,86),(850,121),'Petri dish','Petrischale'),((500,130),(900,166),'08 Upper support frame','08 Oberer Auflagerahmen'),((85,355),(220,395),'07 Camera panel','07 Kameraplatte'),((205,410),(775,450),'Camera below panel; lens points up','Kamera unter Platte; Objektiv nach oben'),((480,220),(820,260),'Sensors above panel','Sensoren über Platte'),((1105,95),(1490,135),'05 Centre divider','05 Trennwand'),((850,275),(979,315),'Raspberry Pi','Raspberry Pi'),((910,558),(1480,600),'Card slot faces down','Kartenschacht nach unten')]
 for pos,end,en,de in labels:
  d.rectangle((*pos,*end),fill='white');text(d,pos,en if lang=='en' else de,25,end[0]-pos[0])
 im.save(out/'orientation.png')
 im=Image.open(src/'hinge.png').convert('RGB');d=ImageDraw.Draw(im)
 labels=[((40,20),(410,57),'Flush hinge · dimensions (mm)','Scharnier · Maße (mm)'),((35,185),(145,225),'Pitch 40','Abstand 40'),((748,445),(1090,485),'Pitch 17','Lochabstand 17'),((430,40),(540,73),'Ø 6','Ø 6'),((40,752),(1080,810),'Large leaf on door; small leaf on side panel. Metal holes: approx. 5 mm.','Großes Blatt an Tür, kleines an Seitenplatte. Metallbohrungen: ca. 5 mm.')]
 for pos,end,en,de in labels:
  d.rectangle((*pos,*end),fill='white');text(d,pos,en if lang=='en' else de,25,end[0]-pos[0])
 # Restore dimension labels and the line beneath the original title area.
 d.rectangle((40,5,415,72),fill='white')
 text(d,(40,5),'Flush hinge · dimensions (mm)' if lang=='en' else 'Scharnier · Maße (mm)',25,370)
 text(d,(290,40),'19',25)
 d.line((150,100,150,700),fill='#315966',width=2)
 im.save(out/'hinge.png')
 im=Image.new('RGB',(1500,310),'white');d=ImageDraw.Draw(im)
 steps=['01 Write OS\nAccount, network, SSH','02 Insert card\nBoot and test network','03 Shut down, unplug\nMount and wire boards','04 Deploy and test\nThen close enclosure'] if lang=='en' else ['01 System schreiben\nKonto, Netzwerk, SSH','02 Karte einsetzen\nStarten, Netzwerk prüfen','03 Herunterfahren\nStrom trennen, montieren','04 Bereitstellen, testen\nDann Gehäuse schließen']
 for i,s in enumerate(steps):
  x=15+i*375;d.rounded_rectangle((x,65,x+330,230),radius=12,fill='#e5f1ef',outline='#6c9897',width=2)
  for j,line in enumerate(s.splitlines()):text(d,(x+15,108+j*40),line,24,300)
  if i<3:text(d,(x+338,126),'→',25)
 im.save(out/'preparation.png')
print('Localized eight diagrams for each language')
