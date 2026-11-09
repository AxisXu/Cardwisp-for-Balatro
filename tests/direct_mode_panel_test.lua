-- 复现 issue #1：有 cardwisp-model.json 时面板走直连，设置与独立窗口不可用，但必须看得见、说得清原因。
-- 这里用真实的 modules/model.lua 决定模式，不用假的 is_bridge，否则测不到用户实际走的路径。
local w,h=1280,720
local mouse_x,mouse_y=0,0
local colour={1,1,1,1}
local rects,lines,printed={}, {}, {}
local function nop()end
local function record_colour(r,g,b,a)
 if type(r)=='table' then colour={r[1],r[2],r[3],r[4]} else colour={r,g,b,a} end
end
local font={getHeight=function()return 16 end,getWidth=function(_,s)return #s*8 end,getWrap=function(_,s)return 100,{s} end}
love={graphics=setmetatable({getDimensions=function()return w,h end,newFont=function()return font end,setColor=record_colour,
  rectangle=function(_,x,y,width,height)rects[#rects+1]={x=x,y=y,w=width,h=height,colour=colour}end,
  line=function(x,y)lines[#lines+1]={x=x,y=y,colour=colour}end,
  printf=function(value)printed[#printed+1]=value end},{__index=function()return nop end}),
 timer={getTime=function()return 10 end},
 keyboard={setTextInput=nop,setKeyRepeat=nop,hasKeyRepeat=function()return false end},
 mouse={getPosition=function()return mouse_x,mouse_y end},system={openURL=function()error('直连模式不应打开任何窗口')end}}
G={STAGE=1,STAGES={RUN=1},GAME={dollars=7},SETTINGS={language='zh_CN'},CONTROLLER={locks={}}}
local core=dofile('modules/core.lua')
local locales={['en-us']=dofile('locales/en-us.lua'),zh_CN=dofile('locales/zh_CN.lua')}
local tr=core.translator(locales)

local DIRECT='direct-config'
local BAD='bad-config'
local function panel(raw)
 local sent=0
 local model=dofile('modules/model.lua')({
  read_config=function()return raw end,
  decode=function(value)
   if value==BAD then error('not json') end
   return {url='https://api.example.com/v1/chat/completions',model='step-5-preview',api_key='k',timeout_seconds=120}
  end,
  encode=function()return '{}' end,
  request=function()sent=sent+1 end,
 })
 local p=dofile('modules/panel.lua')(core,tr,model);p.open=true
 return p,model,function()return sent end
end
local function centre(rect)return rect.x+rect.w/2,rect.y+rect.h/2 end
local function same(a,b)for i=1,3 do if a[i]~=b[i] then return false end end;return true end
local function icon_colours(p,rect)
 rects,lines={}, {}
 mouse_x,mouse_y=0,0;p:draw()
 local fill,stroke
 for _,item in ipairs(rects)do if item.x==rect.x and item.y==rect.y and item.w==rect.w then fill=item.colour end end
 for _,item in ipairs(lines)do
  if item.x>=rect.x and item.x<=rect.x+rect.w and item.y>=rect.y and item.y<=rect.y+rect.h then stroke=item.colour end
 end
 return fill,stroke
end

-- 真实配置确实走直连
local direct,direct_model,direct_sent=panel(DIRECT)
assert(direct_model:is_bridge()==false,'有配置文件时应为直连')
local bridge,bridge_model=panel(nil)
assert(bridge_model:is_bridge()==true,'没有配置文件时应走桥接')
local ui=direct:settings_regions()

-- 直连：两个图标都要画出来，而且看得出不可用（与桥接时的外观不同）
for _,key in ipairs({'gear','popout'})do
 local fill,stroke=icon_colours(direct,ui[key])
 assert(fill and stroke,key..' 在直连模式下也应画出来')
 local bridge_fill,bridge_stroke=icon_colours(bridge,bridge:settings_regions()[key])
 assert(bridge_fill and bridge_stroke,key..' 在桥接模式下应画出来')
 assert(not same(fill,bridge_fill) or not same(stroke,bridge_stroke),key..' 直连时应置灰，与可用状态区分开')
end

-- 回归：发送按钮是红底亮色图标，两种模式都不能被置灰逻辑影响
for name,item in pairs({direct=direct,bridge=bridge})do
 local _,_,send=item:regions()
 local fill,stroke=icon_colours(item,send)
 assert(fill and fill[1]>fill[2]+0.2 and fill[1]>fill[3]+0.2,name..' 发送按钮应保持红底')
 assert(stroke and stroke[1]>0.8,name..' 发送按钮图标应保持亮色')
end

-- 直连：悬停说明原因；桥接：文案不变
for _,locale in ipairs({'zh_CN','en-us'})do
 G.SETTINGS.language=locale
 assert(direct:header_tooltip(centre(ui.gear))==tr(locale,'tip_settings_bridge'),locale..' 齿轮应说明需要桥接程序')
 assert(direct:header_tooltip(centre(ui.popout))==tr(locale,'tip_outside_bridge'),locale..' 弹出按钮应说明需要桥接程序')
 assert(locales[locale].tip_settings_bridge and locales[locale].tip_outside_bridge,locale..' 两种语言都要有文案，不能靠回退')
 assert(tr(locale,'tip_settings_bridge'):find('README',1,true) and tr(locale,'tip_outside_bridge'):find('README',1,true),'提示要指向 README')
 local bridge_ui=bridge:settings_regions()
 assert(bridge:header_tooltip(centre(bridge_ui.gear))==tr(locale,'tip_settings'))
 assert(bridge:header_tooltip(centre(bridge_ui.popout))==tr(locale,'tip_outside'))
end
G.SETTINGS.language='zh_CN'

-- 直连：点击被面板吃掉，不打开设置、不切窗口、不发请求、不影响输入框
direct:focus(true)
for _,key in ipairs({'gear','popout'})do
 local x,y=centre(ui[key])
 assert(direct:mousepressed(x,y,1)==true,key..' 的点击不能漏给游戏')
 assert(not direct.settings_open,key..' 不应打开设置')
 assert(direct.open,key..' 不应收起面板')
 assert(not direct.settings_error,key..' 不应报错')
 assert(direct.focused,key..' 不应抢走输入框焦点')
 assert(direct_sent()==0,key..' 不应发出任何请求')
end
direct:focus(false)

-- 配置写错时同样不会崩，图标照样有说明
local bad,bad_model=panel(BAD)
assert(bad_model:is_bridge()==false)
bad:draw()
assert(bad:header_tooltip(centre(bad:settings_regions().gear))==tr('zh_CN','tip_settings_bridge'))

-- 提示框要完整落在屏幕内：各种窗口、面板宽度与语言
for _,size in ipairs({{640,480},{800,600},{1280,720},{1920,1080},{3840,2160}})do
 w,h=size[1],size[2]
 for _,width in ipairs({390,520,760})do
  direct.width=width
  for _,locale in ipairs({'zh_CN','en-us'})do
   G.SETTINGS.language=locale
   local regions=direct:settings_regions()
   for _,key in ipairs({'gear','popout'})do
    mouse_x,mouse_y=centre(regions[key])
    rects,printed={}, {}
    direct:draw()
    local tip=direct:header_tooltip(mouse_x,mouse_y)
    local shown=false
    for _,value in ipairs(printed)do if value==tip then shown=true end end
    assert(shown,'悬停时应真的把提示画出来')
    local outer=rects[#rects-1]
    assert(outer.x>=0 and outer.x+outer.w<=w and outer.y>=0 and outer.y+outer.h<=h,
     ('提示框超出屏幕：%dx%d 面板 %d %s %s'):format(w,h,width,locale,key))
   end
  end
 end
end
G.SETTINGS.language='zh_CN';w,h=1280,720

print('直连模式面板测试通过：图标置灰可见、悬停说明原因、点击无副作用、提示不出屏')
