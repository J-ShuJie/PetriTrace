"""Illustrations only: uses unchanged CAD modules from the supplied source folder."""
from pathlib import Path
import subprocess, shutil
from PIL import Image, ImageDraw, ImageFont, ImageChops

PARTS=[('01','左侧板','side_panel_2d(false,joint_system)'),('02','合页侧板','side_panel_2d(true,joint_system)'),
('03','底板','bottom_panel_2d(joint_system)'),('04','顶板','top_panel_2d(joint_system)'),
('05','中隔板','central_divider_2d()'),('06','大异形前板','front_panel_2d()'),
('07','下层相机板','camera_shelf_2d_v50()'),('08','上层框板','upper_shelf_2d()'),
('09','屏幕第一层','screen_outer_frame_2d()'),('10','屏幕第二层','screen_structural_frame_2d()'),
('11','屏幕第三层','screen_spacer_frame_2d()'),('12','屏幕第四层','screen_rear_carrier_2d()'),
('13','门板','door_panel_power_v60()'),('14','把手立板','handle_blade_2d_v42()'),
('15','把手回折板','handle_return_2d_v42()'),('16','门侧磁铁板','door_magnet_carrier_2d_v42()'),
('17','箱体磁铁前板','body_magnet_carrier_2d_v42()'),('18','箱体磁铁背板','body_magnet_backplate_2d_v42()'),
('19','屏幕第五层','screen_fifth_2d_v52()')]

RENUMBER={19:13,13:14,14:15,15:16,16:17,17:18,18:19}
PARTS=sorted([(f'{RENUMBER.get(int(n),int(n)):02}',t,b) for n,t,b in PARTS])

def generate(cad_dir, tmp, assets):
    shutil.copytree(cad_dir/'lib',tmp/'lib',dirs_exist_ok=True)
    base='''joint_system="tnut"; geometry_revision=3; panel_t=3; slot_w=2.9; finger_w=10;
large_leaf_on_door_v49=true; show_fastener_references=false; show_sensor_references=false;
show_hinge_reference_v60=false; show_rpi_reference_v62=false; power_exit_v60="door";
$hinge_variant_v63="main"; explode_distance=0;
include <lib/laser_cut_v63_hinge_screen_common.scad>
view_z=35; tag_size=15;
module tag(t,p) {translate(p) rotate([65,0,view_z]) {
color("white") translate([-1,-1,-.5]) cube([len(t)*tag_size*.7+2,tag_size+2,.3]);
color("#173f45") linear_extrude(.2) text(t,size=tag_size,font="Liberation Sans:style=Bold");}}
'''
    def render(name,body,camera='0,0,0,65,0,35,700',size='1600,1200',out=None):
        f=tmp/(name+'.scad')
        body=body.replace('09-12,19','09-13')
        f.write_text(base+body,encoding='utf-8')
        path=out or assets/(name+'.png')
        r=subprocess.run(['C:/Program Files/OpenSCAD/openscad.com','-o',str(path),'--imgsize='+size,'--viewall','--autocenter','--projection=o','--colorscheme=Tomorrow','--camera='+camera,str(f)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        if r.returncode or 'WARNING:' in r.stderr: raise RuntimeError(r.stderr)
        if not name.startswith('part-'):
            im=Image.open(path).convert('RGB')
            box=ImageChops.difference(im,Image.new('RGB',im.size,im.getpixel((0,0)))).getbbox()
            if box:im.crop((max(0,box[0]-35),max(0,box[1]-35),min(im.width,box[2]+35),min(im.height,box[3]+35))).save(path)
    render('assembly','laser_cut_version_v63("assembly");')
    render('exploded','''
side_panel_3d(-115,false,joint_system); tag("01",[-115,-20,205]);
side_panel_3d(270,true,joint_system); tag("02",[270,-20,205]);
color("#839ca7") translate([0,0,-90]) linear_extrude(3) bottom_panel_2d(joint_system); tag("03",[30,-10,-85]);
color("#839ca7") translate([0,0,320]) linear_extrude(3) top_panel_2d(joint_system); tag("04",[30,-10,325]);
color("#75a8b1") yz_panel_3d(divider_x) central_divider_2d(); tag("05",[98,-8,205]);
color("#adb1bc") xz_panel_3d(-235) front_panel_2d(); tag("06",[50,-235,205]);
color("#66aaa0") translate([0,0,25]) linear_extrude(3) camera_shelf_2d_v50(); tag("07",[0,-10,30]);
color("#66aaa0") translate([-30,0,245]) linear_extrude(3) upper_shelf_2d(); tag("08",[-35,0,250]);
translate([0,-340,0]) screen_stack_3d(); tag("09-12,19",[0,-375,25]);
color("#b97f64") translate([70,0,0]) xz_panel_3d(255) door_panel_power_v60(); tag("14",[190,255,205]);
color("#d6ad68") translate([-10,210,0]) yz_panel_3d(handle_blade_x0_v42)
 translate([door_outer_y_v42,handle_z0_v42]) handle_blade_2d_v42(); tag("15",[0,315,180]);
color("#c8984d") translate([160,260,0]) xz_panel_3d(door_outer_y_v42+handle_clear_depth_v42)
 translate([handle_blade_x0_v42,handle_z0_v42]) handle_return_2d_v42(); tag("16",[170,385,180]);
color("#719da9") translate([70,100,0]) xz_panel_3d(door_magnet_carrier_y_v42)
 door_magnet_carrier_2d_v42(); tag("17",[75,190,125]);
color("#3ba3a3") translate([-70,25,0]) xz_panel_3d(body_magnet_carrier_y_v42)
 body_magnet_carrier_2d_v42(); tag("18",[-60,120,125]);
color("#d6ad68") translate([-95,-25,0]) xz_panel_3d(body_magnet_back_y_v42)
 body_magnet_backplate_2d_v42(); tag("19",[-90,60,125]);

''')
    render('screen','''for(i=[0:4]) {
translate([0,0,i*32]) color([.25+i*.1,.62,.65]) linear_extrude(3)
if(i==4) screen_fifth_2d_v52(); else screen_layer_2d_v51(i);
tag(str(i+9<10?"0":"",i+9),[-32,0,i*32+4]);}
''')
    def paired(name,left,right):
        angle=215 if name=='handle' else 135 if name=='hinge-mount' else 35
        prefix=f'view_z={angle};tag_size='+('6;' if 'magnet' in name else '10;')
        render(name+'-exploded',prefix+left,camera=f'0,0,0,65,0,{angle},700',out=tmp/(name+'-exploded.png'))
        render(name+'-assembled',prefix+right,camera=f'0,0,0,65,0,{angle},700',out=tmp/(name+'-assembled.png'))
        board=Image.new('RGB',(1800,1050),'white');draw=ImageDraw.Draw(board)
        heading=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',34)
        for i,(suffix,title) in enumerate([('-exploded','分解与对位'),('-assembled','装配位置')]):
            im=Image.open(tmp/(name+suffix+'.png')).convert('RGB')
            scale=min(865/im.width,930/im.height)
            im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
            board.paste(im,(i*900+(900-im.width)//2,95+(930-im.height)//2))
            draw.text((i*900+35,25),title,font=heading,fill='#173f45')
        board.save(assets/(name+'.png'))
    door_panel='color("#b97f64") xz_panel_3d(door_inner_y_v42) door_panel_power_v60(); tag("14",[130,98,200]);'
    handle='\ncolor("#d6ad68") yz_panel_3d(handle_blade_x0_v42)\n translate([door_outer_y_v42,handle_z0_v42]) handle_blade_2d_v42();\ncolor("#a98045") xz_panel_3d(door_outer_y_v42+handle_clear_depth_v42)\n translate([handle_blade_x0_v42,handle_z0_v42]) handle_return_2d_v42();\n'
    paired('handle',door_panel+'translate([30,50,0]) {'+handle+'} tag("15",[60,210,175]); tag("16",[65,210,135]);',
        door_panel+handle+'tag("15",[30,155,177]); tag("16",[35,155,135]);')
    side='intersection(){side_panel_3d(0,false,joint_system);translate([-5,45,50])cube([15,70,100]);} tag("01",[10,35,150]);'
    front='color("#3ba3a3") xz_panel_3d(body_magnet_carrier_y_v42) body_magnet_carrier_2d_v42();'
    back='color("#d6ad68") xz_panel_3d(body_magnet_back_y_v42) body_magnet_backplate_2d_v42();'
    paired('body-magnet',side+'translate([25,-20,0]){'+back+'} translate([50,20,0]){'+front+'} tag("19",[25,60,125]);tag("18",[50,115,125]);',
        side+front+back+'tag("18",[17,98,122]);tag("19",[17,65,85]);')
    door_crop='intersection(){color("#b97f64")xz_panel_3d(door_inner_y_v42)door_panel_power_v60();translate([0,80,55])cube([65,30,90]);}tag("14",[50,65,145]);'
    moving='color("#719da9")xz_panel_3d(door_magnet_carrier_y_v42)door_magnet_carrier_2d_v42();'
    paired('door-magnet',door_crop+'translate([0,-40,0]){'+moving+'}tag("17",[25,40,125]);',
        door_crop+moving+'tag("17",[28,70,123]);')
    hinge_panels='color("#b97f64")xz_panel_3d(door_inner_y_v42)door_panel_power_v60();side_panel_3d(outer_width-panel_t,true,joint_system);'
    paired('hinge-mount',
        'translate([-45,35,0]){color("#b97f64")xz_panel_3d(door_inner_y_v42)door_panel_power_v60();}translate([40,-35,0])side_panel_3d(outer_width-panel_t,true,joint_system);hinge_hardware_reference_v60();tag("14",[100,135,200]);tag("02",[200,50,200]);',
        hinge_panels+'hinge_hardware_reference_v60();tag("14",[120,100,200]);tag("02",[160,40,200]);')
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',25)
    sheet=Image.new('RGB',(1500,1800),'white'); d=ImageDraw.Draw(sheet)
    for i,(num,title,body) in enumerate(PARTS):
        target=tmp/('part-'+num+'.png')
        render('part-'+num,'color("#77a6a8") linear_extrude(3) '+body+';',camera='0,0,0,0,0,0,500',size='340,285',out=target)
        x=(i%4)*375; y=(i//4)*360
        sheet.paste(Image.open(target).convert('RGB'),(x+17,y+40))
        d.text((x+18,y+6),num+' '+title,font=font,fill='#173f45')
    sheet.save(assets/'parts.png')
    flow=Image.new('RGB',(1500,310),'white'); d=ImageDraw.Draw(flow)
    items=['01 写入系统\n设置账户、网络、SSH','02 插入存储卡\n通电确认网络','03 关机并断电\n安装主板与连接线','04 部署和试拍\n检查后封合']
    for i,t in enumerate(items):
        x=15+i*375; d.rounded_rectangle((x,65,x+330,230),radius=12,fill='#e5f1ef',outline='#6c9897',width=2)
        d.multiline_text((x+18,108),t,font=font,fill='#173f45',spacing=15)
        if i<3: d.text((x+338,126),'→',font=font,fill='#173f45')
    flow.save(assets/'preparation.png')
    orientation=Image.new('RGB',(1500,650),'white');d=ImageDraw.Draw(orientation)
    d.text((35,25),'安装方向 · 简化剖面示意（非比例图）',font=font,fill='#173f45')
    # The dish rests on the upper frame; the camera below looks upward.
    d.rectangle((120,132,250,152),fill='#8ba6aa')
    d.rectangle((390,132,465,152),fill='#8ba6aa')
    d.rounded_rectangle((205,88,435,132),radius=10,fill='#e6ecec',outline='#315966',width=3)
    d.line((210,100,430,100),fill='#71999c',width=2)
    d.text((500,86),'培养皿',font=font,fill='#173f45')
    d.text((500,130),'08 上层框板承托',font=font,fill='#173f45')
    d.line((480,105,435,105),fill='#315966',width=2)
    d.line((485,148,430,145),fill='#315966',width=2)
    d.rectangle((80,315,710,345),fill='#8ba6aa');d.text((85,355),'07 相机板',font=font,fill='#173f45')
    d.rectangle((230,345,390,390),fill='#628e6d');d.rectangle((290,290,335,345),fill='#3f5558')
    d.line((312,285,312,170),fill='#173f45',width=5);d.polygon([(312,156),(300,180),(324,180)],fill='#173f45')
    d.text((205,410),'相机在板下，镜头向上',font=font,fill='#173f45')
    d.rectangle((505,265,635,295),fill='#ddaf71');d.line((520,295,520,315),fill='#444444',width=4)
    d.text((480,220),'传感器在板上',font=font,fill='#173f45')
    d.rectangle((1160,145,1186,480),fill='#789ba5');d.text((1105,95),'05 中隔板',font=font,fill='#173f45')
    d.rectangle((984,240,1030,458),fill='#628e6d');d.text((850,275),'树莓派',font=font,fill='#173f45')
    d.rectangle((990,440,1024,480),fill='#b59973');d.line((1010,490,1010,540),fill='#173f45',width=4)
    d.text((910,558),'存储卡侧朝下',font=font,fill='#173f45')
    orientation.save(assets/'orientation.png')
    hinge=Image.new('RGB',(1100,850),'white');d=ImageDraw.Draw(hinge)
    d.text((40,20),'子母合页 · 尺寸参考（mm）',font=font,fill='#173f45')
    d.rectangle((200,100,428,700),fill='#aec7ce',outline='#315966',width=3)
    d.rectangle((250,244,428,556),fill='white',outline='#315966',width=3)
    d.rectangle((428,100,500,700),fill='#718c97',outline='#315966',width=3)
    d.rectangle((500,244,644,556),fill='#ddbd85',outline='#315966',width=3)
    for x,y in [(314,160),(314,640),(569,298),(569,502)]:d.ellipse((x-30,y-30,x+30,y+30),fill='white',outline='#315966',width=3)
    def dim(a,b,label,pos):
        d.line((a,b),fill='#315966',width=2)
        for x,y in [a,b]:d.ellipse((x-4,y-4,x+4,y+4),fill='#315966')
        d.text(pos,label,font=font,fill='#173f45')
    dim((150,100),(150,700),'50',(92,370));dim((705,244),(705,556),'26',(722,385))
    dim((314,160),(314,640),'孔距40',(35,185));dim((569,298),(569,502),'孔距17',(748,445))
    dim((200,75),(428,75),'19',(290,40));dim((428,75),(500,75),'轴径6',(430,40))
    dim((500,210),(644,210),'12',(553,165))
    d.text((40,752),'大片装门板，小片装箱体侧板；金属通孔实测约5 mm。',font=font,fill='#173f45')

    hinge.save(assets/'hinge.png')
