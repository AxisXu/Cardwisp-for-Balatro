local clock=10
love={timer={getTime=function()return clock end},graphics={getDimensions=function()return 1280,720 end},
 keyboard={setTextInput=function()end,setKeyRepeat=function()end}}
G={STAGE=1,STAGES={RUN=1},STATE=4,STATES={SHOP=4,BUFFOON_PACK=18},
 GAME={dollars=20,pack_choices=1,round_resets={ante=1}},SETTINGS={language='zh_CN'},CONTROLLER={locks={}}}
local core=dofile('modules/core.lua')
local tr=core.translator({['en-us']=dofile('locales/en-us.lua'),zh_CN=dofile('locales/zh_CN.lua')})
local published={}
local fake={
 is_bridge=function()return true end,
 configuration=function()return {model='gpt-6-sol',timeout_seconds=180}end,
 publish=function(_,_,snapshot,_,callback)published[#published+1]=snapshot;callback(true,{});return true end,
 poll=function(_,callback)callback(true,{run_id=tostring(G.GAME),connected=true,messages={},pending=false,settings={display_mode='inside',model='gpt-6-sol',effort='high'}});return true end,
}
local panel=dofile('modules/panel.lua')(core,tr,fake)
panel:update();assert(#published==1 and published[1].phase=='shop')
G.STATE=18;G.pack_cards={cards={}}
panel:update();assert(#published==2 and published[2].phase=='pack')
G.pack_cards.cards[1]={config={center={key='j_first',set='Joker'}},ability={set='Joker'}}
panel:update();assert(#published==3 and published[3].pack.options[1].key=='j_first')
G.pack_cards.cards[2]={config={center={key='j_second',set='Joker'}},ability={set='Joker'}}
panel:update();assert(#published==4 and published[4].pack.options[2].key=='j_second')
print('场景同步测试通过：开包状态与候选牌出现后立即发布')
