local calls={key=0,mouse=0,release=0,text=0}
local mx,my=0,0
local time=10
love={graphics={getDimensions=function()return 1280,720 end},timer={getTime=function()return time end},
 filesystem={read=function()return nil end},
 keyboard={setTextInput=function()end,setKeyRepeat=function()end,hasKeyRepeat=function()return false end,isDown=function()return false end},
 mouse={getPosition=function()return mx,my end},system={getClipboardText=function()return '中文' end},
 keypressed=function()calls.key=calls.key+1 end,mousepressed=function()calls.mouse=calls.mouse+1 end,
 mousereleased=function()calls.release=calls.release+1 end,textinput=function()calls.text=calls.text+1 end}
G={STAGE=1,STAGES={RUN=1},STATE=4,STATES={SHOP=4},GAME={dollars=20,round_resets={ante=1}},SETTINGS={language='zh_CN'},CONTROLLER={locks={}}}
JSON={encode=function()return '{}' end,decode=function()return {} end}
SMODS={current_mod={},load_file=function(path)return loadfile(path)end}
dofile('main.lua')
local p=SMODS.current_mod.assistant
local function eq(a,b)assert(a==b,tostring(a)..' ~= '..tostring(b))end
love.keypressed('f8');love.keyreleased('f8');eq(p.open,true);eq(calls.key,0)
eq(p.editor.text,'这个商店怎么选？');eq(p.suggested,true)
G.STATES.SELECTING_HAND=1;G.STATES.BLIND_SELECT=7
G.STATE=1;p:update();eq(p.editor.text,'这手牌建议怎么出？')
G.STATE=7;p:update();eq(p.editor.text,'这个盲注值得跳过吗？')
G.STATE=4;p:update();eq(p.editor.text,'这个商店怎么选？')
G.STATES.BUFFOON_PACK=18;G.STATE=18;G.GAME.pack_choices=1
G.localization={descriptions={Spectral={c_hex={name='妖法',text={'随机为一张{C:attention}小丑牌{}添加','{C:attention}多彩{}，摧毁其他小丑牌'}}},Joker={j_choice={name='开心小丑'}}}}
G.pack_cards={cards={{config={center={key='j_choice',set='Joker'}},ability={set='Joker'}}}}
G.consumeables={config={card_limit=2},cards={{config={center={key='c_hex',set='Spectral'}},ability={set='Spectral'}}}}
p:update();eq(p.editor.text,'这个卡包选哪张？')
local snapshot=p:read_snapshot();eq(snapshot.pack.options[1].name,'开心小丑')
eq(snapshot.consumables[1].name,'妖法');eq(snapshot.consumables[1].description,'随机为一张小丑牌添加 多彩，摧毁其他小丑牌')
-- 原版卡包的 set 是 Booster，但名称与文案存于 descriptions.Other。
G.localization.descriptions.Other={
 p_arcana_mega={name='超级秘术包',text={'选择{C:attention}#1#{}张塔罗牌'}},
 p_standard_jumbo={name='巨型标准包',text={'从最多{C:attention}#2#张{}游戏牌中选择'}},
 p_celestial_normal={name='天体包',text={'选择{C:attention}#1#{}张星球牌'}}}
G.shop_booster={cards={
 {config={center={key='p_arcana_mega_2',set='Booster'}},cost=8},
 {config={center={key='p_standard_jumbo_2',set='Booster'}},cost=6},
 {config={center={key='p_celestial_normal_4',set='Booster'}},cost=4}}}
G.STATE=4;p:update();eq(p.editor.text,'这个商店怎么选？')
local boosters=p:read_snapshot().shop
eq(boosters[1].name,'超级秘术包')
eq(boosters[2].name,'巨型标准包');eq(boosters[2].description,'从最多?张游戏牌中选择')
eq(boosters[3].name,'天体包');eq(boosters[3].description_unresolved,true)
G.localization.misc={ranks={Ace='A'},suits_plural={Hearts='红桃'}}
G.playing_cards={{config={center={key='c_base',set='Default'}},ability={set='Default'},base={value='Ace',suit='Hearts'}}}
eq(p:read_snapshot().deck_catalog[1].name,'A♥')
G.localization.descriptions.Joker.j_dynamic={name='升势',text={'增加{C:mult}+#1#{}倍率'}}
G.jokers={config={card_limit=5},cards={{config={center={key='j_dynamic',set='Joker'}},ability={set='Joker',extra=4}}}}
local dynamic=p:read_snapshot().owned[1]
eq(dynamic.description,'增加+?倍率');eq(dynamic.description_unresolved,true);eq(dynamic.values.extra,4)
G.localization.misc.poker_hands={['Two Pair']='两对'}
G.localization.descriptions.Joker.j_trousers={name='备用裤子',text={'如果打出的牌中包含{C:attention}#2#{}','这张小丑获得{C:mult}+#1#{}倍率','（当前为{C:red}+#3#{}倍率）'}}
G.localization.descriptions.Joker.j_runner={name='跑步选手',text={'当前为{C:chips}+#1#{}筹码；每次{C:chips}+#2#{}'}}
G.localization.descriptions.Joker.j_stuntman={name='特技演员',text={'+#1#筹码，手牌上限-#2#'}}
G.localization.descriptions.Joker.j_hologram={name='全息影像',text={'每添加卡牌增加X#1#倍率','（当前为X#2#倍率）'}}
G.jokers.cards={
 {config={center={key='j_trousers',set='Joker'}},ability={set='Joker',extra=2,mult=4}},
 {config={center={key='j_runner',set='Joker'}},ability={set='Joker',extra={chips=45,chip_mod=15}}},
 {config={center={key='j_stuntman',set='Joker'}},ability={set='Joker',extra={chip_mod=250,h_size=2}}},
 {config={center={key='j_hologram',set='Joker'}},ability={set='Joker',extra=0.25,x_mult=1.5}}}
local grown=p:read_snapshot().owned
eq(grown[1].description,'如果打出的牌中包含两对 这张小丑获得+2倍率 （当前为+4倍率）')
eq(grown[1].description_unresolved,nil)
eq(grown[2].description,'当前为+45筹码；每次+15')
eq(grown[3].description,'+250筹码，手牌上限-2')
eq(grown[4].description,'每添加卡牌增加X0.25倍率 （当前为X1.5倍率）')
-- 悬停提示优先取游戏自己生成的文字：消耗品、券、标签不再依赖手写参数表。
G.UIT={T=1,C=2,O=3,R=4};G.MOVEABLES={}
local removed=0
DynaText={};function DynaText.is(self,class)return class==DynaText end
local function dyna(text)return {is=DynaText.is,config={string={text}},remove=function()removed=removed+1 end}end
G.localization.descriptions.Tarot={c_magician={name='魔术师',text={'增强{C:attention}#1#{}张','选定卡牌成为{C:attention}#2#'}}}
local magician={config={center={key='c_magician',set='Tarot'}},ability={set='Tarot'},
 generate_UIBox_ability_table=function(self)
  return {main={{{n=1,config={text='增强'}},{n=2,nodes={{n=3,config={object=dyna('2')}}}},{n=1,config={text='张'}}},
   {{n=1,config={text='选定卡牌成为'}},{n=1,config={text='幸运牌'}}}},
   info={{{{n=1,config={text='幸运牌：'}},{n=1,config={text='1/5几率+20倍率'}}}}}}
 end}
G.consumeables.cards={magician}
local tarot=p:read_snapshot().consumables[1]
eq(tarot.description,'增强2张 选定卡牌成为幸运牌');eq(tarot.description_unresolved,nil);eq(removed,1)
eq(tarot.details[1],'幸运牌：1/5几率+20倍率')
G.localization.descriptions.Voucher={v_grabber={name='抓手',text={'每回合+#1#次出牌'}}}
G.localization.descriptions.Tag={tag_handy={name='灵巧标签',text={'每打出一手+$#1#（当前$#2#）'}}}
G.P_CENTERS={v_grabber={key='v_grabber',set='Voucher',config={extra=1}}}
G.P_TAGS={tag_handy={key='tag_handy',set='Tag',config={dollars_per_hand=1}}}
generate_card_ui=function(center,_,vars,set)
 if center.key=='v_grabber' then eq(set,'Voucher');return {main={{{n=1,config={text='每回合+'}},{n=1,config={text=tostring(center.config.extra)}},{n=1,config={text='次出牌'}}}},info={}} end
 eq(set,'Tag');return {main={{{n=1,config={text='每打出一手+$1（当前$6）'}}}},info={}}
end
G.GAME.used_vouchers={v_grabber=true};G.GAME.tags={{key='tag_handy'}}
local snap=p:read_snapshot()
eq(snap.vouchers[1].description,'每回合+1次出牌');eq(snap.vouchers[1].description_unresolved,nil)
eq(snap.tags[1].description,'每打出一手+$1（当前$6）');eq(snap.tags[1].description_unresolved,nil)
-- 游戏函数报错时退回模板路径，不让面板崩溃。
magician.generate_UIBox_ability_table=function()error('boom')end
local fallback=p:read_snapshot().consumables[1]
eq(fallback.description,'增强?张 选定卡牌成为?');eq(fallback.description_unresolved,true)
G.GAME.used_vouchers=nil;G.GAME.tags=nil;generate_card_ui=nil
-- 牌组说明取自 Back:generate_UI 的节点树。
G.localization.descriptions.Back={b_red={name='红牌组',text={'每回合{C:red}+#1#{}弃牌次数'}}}
G.GAME.selected_back={effect={center={key='b_red'}},generate_UI=function()
 return {n=5,nodes={{n=4,nodes={{n=1,config={text='每回合'}},{n=1,config={text='+1'}},{n=1,config={text='弃牌次数'}}}}}} end}
local with_back=p:read_snapshot()
eq(with_back.back,'红牌组');eq(with_back.back_description,'每回合+1弃牌次数');eq(with_back.back_description_unresolved,nil)
G.GAME.selected_back=nil
G.STATES.BLIND_SELECT=7;G.STATE=7
G.GAME.round_resets={ante=2,blind_choices={Small='bl_small'},blind_states={Small='Select'}}
G.GAME.starting_params={ante_scaling=1};G.P_BLINDS={bl_small={mult=1,dollars=3}}
get_blind_amount=function()return 800 end
eq(p:read_snapshot().blind_options[1].chips,800)
-- 盲注效果用游戏的 raw_descriptions 填参数（如 The Ox 的最常打牌型）。
localize=function(args)
 if type(args)=='table' and args.type=='raw_descriptions' and args.set=='Blind' then
  return {'盲注效果:'..args.key..':'..tostring((args.vars or {})[1])}
 end
end
G.P_BLINDS.bl_small.vars={'两对'}
local option=p:read_snapshot().blind_options[1]
eq(option.effect,'盲注效果:bl_small:两对');eq(option.effect_unresolved,nil)
localize=nil
G.STATE=4
local r=p:rect();love.mousepressed(r.x+40,r.y+r.h-40,1);eq(p.focused,true);eq(calls.mouse,0)
p.editor:select_all();love.textinput('中文问题');eq(p.editor.text,'中文问题');eq(calls.text,0)
G.STATE=1;p:update();eq(p.editor.text,'中文问题');G.STATE=4;p:update()
love.keypressed('r');eq(calls.key,0)
love.textedited('拼音',0,2);love.keypressed('return');eq(#p.session.messages,0)
love.textinput('输入');love.keypressed('return');eq(#p.session.messages,0)
time=time+0.2;love.keypressed('return');eq(#p.session.messages,2)
assert(p.session.messages[2].text:find('连接失败'));eq(p.editor.text,'')
love.keypressed('f8');love.keyreleased('f8');eq(p.open,false)
love.keypressed('f8');love.keyreleased('f8');eq(p.open,true);eq(p.editor.text,'')
love.mousereleased(0,0,1);eq(calls.release,0)
love.mousepressed(0,0,1);eq(calls.mouse,1);eq(p.focused,false)
love.mousereleased(r.x+50,r.y+50,1);eq(calls.release,1)
love.mousepressed(r.x+2,r.y+100,1);love.mousemoved(r.x-100,r.y+100,-102,0);assert(p.width>520);love.mousereleased(0,0,1)
G.OVERLAY_MENU={};p:update();eq(p:visible(),false);eq(G.CONTROLLER.locks.balatro_assistant,nil)
G.OVERLAY_MENU=nil;G.GAME={};p:update();eq(#p.session.messages,0)
love.keypressed('f8');eq(p.open,false)
print('面板回调集成测试通过：焦点、中文、IME、发送、鼠标归属、宽度、生命周期')
