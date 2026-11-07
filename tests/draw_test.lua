local w,h=100,100
local function nop()end
local overlay=false
local dimming=false
local font={getHeight=function()return 16 end,getWidth=function(_,s)return #s*8 end,getWrap=function(_,s,width)
 assert(width>0,'文字换行宽度必须为正')
 local lines={};for part in (s..'\n'):gmatch('(.-)\n')do
  for _=1,math.max(1,math.ceil(#part*8/width))do lines[#lines+1]=part end
 end
 return width,lines
end}
local printed={}
local mouse_x,mouse_y=0,0
love={graphics={getDimensions=function()return w,h end,newFont=function()return font end,
 push=nop,pop=nop,origin=nop,translate=nop,shear=nop,setShader=nop,setColor=function(r,g,b,a)dimming=r==0 and g==0 and b==0 and a==0.53 end,setFont=nop,setLineWidth=nop,printf=function(value)printed[#printed+1]=value end,print=nop,line=nop,
 rectangle=function(_,x,y,width,height)assert(width>=0 and height>=0,'矩形尺寸必须非负');if dimming and x==0 and y==0 and width==w and height==h then overlay=true end end,
 setScissor=function(_,_,width,height)if width then assert(width>=0 and height>=0,'裁切尺寸必须非负')end end},
 timer={getTime=function()return 10 end},keyboard={setTextInput=nop,setKeyRepeat=nop},mouse={getPosition=function()return mouse_x,mouse_y end}}
G={STAGE=1,STAGES={RUN=1},GAME={},SETTINGS={language='zh_CN'},CONTROLLER={locks={}}}
local core=dofile('modules/core.lua');local tr=core.translator({['en-us']=dofile('locales/en-us.lua'),zh_CN=dofile('locales/zh_CN.lua')})
local p=dofile('modules/panel.lua')(core,tr,{is_bridge=function()return true end});p.open=true
for _,size in ipairs({{100,100},{320,240},{640,480},{800,600},{1280,720},{3840,2160}})do
 w,h=size[1],size[2]
 for _,width in ipairs({390,520,760})do
  p.width=width;p.settings_open=false;p:draw();p.settings_open=true;p:draw()
 end
end
assert(overlay,'设置弹窗必须压暗整个游戏背景')
w,h=1280,720
local entry=p:entry();assert(entry.y<40 and entry.x>w/2,'收起入口应位于右上角')
local many={}
for i=1,12 do many[i]={name='超级秘术包',cost=i} end
p.read_snapshot=function()return {phase='shop',ante=1,money=10,jokers=2,slots=5,consumables={{name='妖法'}},shop=many}end
p.width=390;p.settings_open=false
printed={};p:draw()
local summary_cut=false
for _,value in ipairs(printed)do if value:find('…',1,true) then summary_cut=true end end
assert(summary_cut,'长商品摘要必须保持单行并显示省略号')
local r=p:rect();local s=r.scale
mouse_x=r.x+40*s;mouse_y=r.y+120*s
p:mousemoved(mouse_x,mouse_y)
printed={};p:draw()
local full_list=false
for _,value in ipairs(printed)do if value:find('超级秘术包 $12',1,true) then full_list=true end end
assert(full_list,'悬停摘要应显示全部商品')
assert(p.details_maxscroll>0,'完整列表超出浮层时应可滚动')
mouse_y=r.y+165*s
assert(p:wheelmoved(0,-1) and p.details_scroll>0,'浮层应接收滚轮')
p:mousemoved(r.x-20,0);assert(not p.details_open,'移出浮层应收起')
print('绘制边界测试通过：极小窗口到 4K，所有尺寸非负')
