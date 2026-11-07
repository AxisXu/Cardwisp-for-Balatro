local clock=10
local opened
love={timer={getTime=function()return clock end},graphics={getDimensions=function()return 1280,720 end},
 keyboard={setTextInput=function()end,setKeyRepeat=function()end,hasKeyRepeat=function()return false end},
 system={openURL=function(url)opened=url;return true end}}
G={STAGE=1,STAGES={RUN=1},STATE=4,STATES={SHOP=4},GAME={dollars=7,current_round={reroll_cost=5}},SETTINGS={language='zh_CN'},CONTROLLER={locks={}},
 shop_jokers={cards={{config={center={key='j_old',set='Joker'}},cost=5}}}}
local core=dofile('modules/core.lua')
local tr=core.translator({['en-us']=dofile('locales/en-us.lua'),zh_CN=dofile('locales/zh_CN.lua')})
local published={}
local settings={model='gpt-6-sol',effort='high',display_mode='inside',play_goal='clear'}
local fail_settings=false
local fail_open=false
local remote_prompt_used=false
local fake={
 is_bridge=function()return true end,
 configuration=function()return {model=settings.model,timeout_seconds=315}end,
 publish=function(_,run,snapshot,language,callback)
  published[#published+1]={run=run,snapshot=snapshot,language=language};callback(true,{});return true
 end,
 poll=function(_,callback)
  callback(true,{run_id=published[#published].run,messages={{role='assistant',text='外部消息',source='model'}},snapshot={phase='shop'},prompt_used=remote_prompt_used,settings=settings,connected=true,pending=false});return true
 end,
 set_settings=function(_,changes,callback)
  if fail_settings then callback(false,'network');return true end
  for key,value in pairs(changes)do settings[key]=value end
  callback(true,{settings=settings});return true
 end,
 capabilities=function(_,callback)
  callback(true,{models={{id='gpt-6-sol',name='Sol',efforts={'low','medium','high'}},{id='gpt-6-luna',name='Luna',efforts={'low','medium','high'}}},goals={{id='clear',enabled=true},{id='endless',enabled=false}}});return true
 end,
 open_companion=function(_,callback)
  if fail_open then callback(false,'companion_unavailable')
  else callback(true,{kind='native'}) end
  return true
 end,
}
local p=dofile('modules/panel.lua')(core,tr,fake)
p:update()
assert(#published==1 and published[1].snapshot.money==7 and published[1].language=='zh_CN')
clock=10.1;G.GAME.dollars=2;G.GAME.current_round.reroll_cost=6
G.shop_jokers.cards={{config={center={key='j_new',set='Joker'}},cost=4}}
p:update()
assert(#published==2 and published[2].snapshot.shop[1].key=='j_new',
 '重掷后应立即发布新商店，不能等固定一秒轮询')
assert(published[2].snapshot.snapshot_revision>published[1].snapshot.snapshot_revision)
clock=10.2;p:update();assert(#published==2,'商店未变化时不应每帧重复发布')
clock=10
assert(p.session.messages[1].text=='外部消息')
assert(p.remote_settings.model=='gpt-6-sol')
remote_prompt_used=true;clock=11;p:update()
assert(p.editor.text=='' and p.prompt_used,'外部窗口发送后应清除游戏内未使用的预填问题')
p:change_settings({model='gpt-6-luna',effort='medium'})
assert(settings.model=='gpt-6-luna' and p.remote_settings.effort=='medium')
p.pending={id=1,run=p.session.run,started=clock,timeout=315};p.remote_pending=true
p:show_outside()
assert(settings.display_mode=='outside' and opened==nil and not p.open,
 '问题仍在回答时也应能切到游戏外')
p.pending=nil;p.remote_pending=nil
settings.display_mode='inside';clock=12;p:update()
assert(p.open and p.mode=='inside','独立窗口返回后游戏内面板应自动展开')
fail_open=true;p:show_outside()
assert(settings.display_mode=='inside' and p.settings_error=='companion_unavailable' and p.open,
 '独立窗口启动失败时应保留游戏内面板与错误提示')
fail_open=false
p:show_outside()
assert(settings.display_mode=='outside' and not p.open,'再次切到游戏外应收起游戏内面板')
fail_settings=true;p:toggle()
assert(p.open and p.mode=='inside','桥接断线时仍能回到游戏内面板')
fail_settings=false
p:show_inside()
assert(settings.display_mode=='inside' and p.open)
local ui=p:settings_regions()
p:mousepressed(ui.gear.x+ui.gear.w/2,ui.gear.y+ui.gear.h/2,1)
assert(p.settings_open)
p:mousepressed(ui.models[1].x+ui.models[1].w/2,ui.models[1].y+ui.models[1].h/2,1)
assert(settings.model=='gpt-6-sol')
p:mousepressed(ui.efforts[1].x+ui.efforts[1].w/2,ui.efforts[1].y+ui.efforts[1].h/2,1)
assert(settings.effort=='low')
p:mousepressed(ui.goals[2].x+ui.goals[2].w/2,ui.goals[2].y+ui.goals[2].h/2,1)
assert(settings.play_goal=='clear' and p.settings_open,'桥接标记为未开放的目标点了不生效，设置面板也不关闭')
assert(ui.models[1].name=='Sol' and ui.goals[2].enabled==false)
p.remote_pending=true;p.remote_pending_since=clock-7
local content=p:chat_content()
assert(content[#content].thinking and content[#content].text:find('7s',1,true),'回答中应有带等待秒数的思考气泡')
p.remote_pending=nil
assert(not p:chat_content()[#p:chat_content()].thinking)
p:mousepressed(0,0,1)
assert(not p.settings_open,'点击蒙版应关闭设置且不传给游戏')
-- 标题栏：设置、游戏外、收起三个图标从左到右排列；游戏外按钮一点就切出去，鼠标悬停有文字提示
local _,_,_,close=p:regions();ui=p:settings_regions()
assert(ui.gear.x+ui.gear.w<=ui.popout.x and ui.popout.x+ui.popout.w<=close.x,'游戏外按钮应在设置与收起之间')
assert(ui.outside==nil and ui.inside==nil,'设置菜单里不再有位置一栏')
assert(p:header_tooltip(ui.popout.x+2,ui.popout.y+2)==tr('zh_CN','tip_outside'))
assert(p:header_tooltip(ui.gear.x+2,ui.gear.y+2)==tr('zh_CN','tip_settings'))
assert(p:header_tooltip(close.x+2,close.y+2)==tr('zh_CN','tip_collapse'))
assert(p:header_tooltip(0,0)==nil)
p:show_inside()
p:mousepressed(ui.popout.x+ui.popout.w/2,ui.popout.y+ui.popout.h/2,1)
assert(settings.display_mode=='outside' and not p.open,'点游戏外按钮应切到独立窗口')
p:show_inside()
print('设置面板测试通过：模型/强度、共享会话与独立窗口切换')
