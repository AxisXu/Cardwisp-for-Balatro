local clock=10
love={timer={getTime=function()return clock end},graphics={getDimensions=function()return 1280,720 end},
 keyboard={setTextInput=function()end,setKeyRepeat=function()end}}
G={STAGE=1,STAGES={RUN=1},GAME={dollars=20},SETTINGS={language='zh_CN'},CONTROLLER={locks={}}}
local core=dofile('modules/core.lua')
local tr=core.translator({['en-us']=dofile('locales/en-us.lua'),zh_CN=dofile('locales/zh_CN.lua')})
local callback,requests,snapshot= nil,0,nil
local fake={
 configuration=function()return {model='test-model',timeout_seconds=180}end,
 ask=function(_,question,state,language,history,done)
  requests=requests+1;callback=done;snapshot=state
  assert(question=='买哪个？' or question=='下一局？')
  assert(language=='zh_CN');assert(#history==0)
  return true
 end,
}
local p=dofile('modules/panel.lua')(core,tr,fake)
p:update();p:submit('买哪个？');assert(#p.session.messages==1);assert(p.pending)
assert(snapshot.money==20)
p:submit('买哪个？');assert(requests==1,'请求中不应重复发送')
callback(true,'先买左边');assert(#p.session.messages==2)
assert(p.session.messages[2].text=='先买左边' and p.session.messages[2].source=='model')
p.session:sync({});p:submit('下一局？');local old=callback
G.GAME={};p:update();old(true,'上一局的回答')
assert(#p.session.messages==0,'上一局的异步回复不能进入新牌局')
p:submit('下一局？');clock=clock+181;p:update();assert(not p.pending)
assert(p.session.messages[2].text:find('180 秒'))
callback(true,'超时后的回答');assert(#p.session.messages==2)
print('模型面板测试通过：异步回复、重复发送、换局与超时')
