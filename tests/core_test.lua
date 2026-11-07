local core = dofile('modules/core.lua')
local n = 0
local function test(name, fn) fn(); n=n+1; print('通过：'..name) end
local function eq(a,b) assert(a==b, tostring(a)..' ~= '..tostring(b)) end

test('多字节光标移动、插入和删除', function()
 local e=core.editor('中文🃏A'); e:move(-1); e:backspace(); eq(e.text,'中文A')
 e:insert('测试'); eq(e.text,'中文测试A'); e:home(); e:delete(); eq(e.text,'文测试A')
 e:finish(); e:backspace(); eq(e.text,'文测试')
end)
test('选中替换与单行粘贴上限',function()
 local e=core.editor('旧文字'); e:select_all(); e:insert('新\n内容\t好'); eq(e.text,'新 内容 好')
 e:insert(string.rep('中',3000)); assert(#e.text<=core.MAX_INPUT_BYTES)
 local count=0; for _ in e.text:gmatch('[%z\1-\127\194-\244][\128-\191]*') do count=count+1 end
 assert(count>100)
end)
test('小窗口与宽度调整始终留在屏幕内',function()
 for _,size in ipairs({{800,600},{1280,720},{1920,1080},{3840,2160}}) do
  for _,width in ipairs({100,520,9999}) do
   local r=core.layout(size[1],size[2],width)
   assert(r.x>=0 and r.y>=0 and r.x+r.w<=size[1] and r.y+r.h<=size[2])
   assert(r.w>=260 and r.h>=300)
  end
 end
end)
test('长摘要按字形宽度截断，且不截断中文字符',function()
 local full='妖法 · 超级秘术包 $8'
 local fitted,cut=core.fit_line(full,16,function(value)return #value end)
 eq(fitted,'妖法 · 超…');eq(cut,true)
 eq(core.fit_line('妖法',44,function(value)return #value end),'妖法')
end)
test('局面快照只包含公开字段且不修改游戏',function()
 local g={STATE=4,STATES={SHOP=4},GAME={dollars=71,round_resets={ante=5},secret='hidden'},
 jokers={cards={{config={center={key='j_owned',set='Joker'}},sell_cost=3}},config={card_limit=6}}, shop_jokers={cards={{config={center={key='j_joker',set='Joker'}},cost=4}}}, deck={cards={'secret order'}}}
 local s=core.snapshot(g,function(key) return '牌名:'..key end)
 eq(s.money,71);eq(s.ante,5);eq(s.jokers,1);eq(s.slots,6);eq(s.phase,'shop');eq(s.shop[1].name,'牌名:j_joker')
 eq(s.owned[1].key,'j_owned');eq(s.owned[1].name,'牌名:j_owned');eq(s.owned[1].sell_cost,3)
 eq(s.deck,nil);eq(s.secret,nil);eq(g.GAME.secret,'hidden')
 g.STATE=8;eq(#core.snapshot(g,function(k)return k end).shop,0)
end)
test('盖住的手牌不泄露花色和点数',function()
 local g={STATE=2,STATES={SHOP=4,SELECTING_HAND=2},GAME={current_round={hands_left=2,discards_left=1},blind={name='The Fish',chips=10000}},hand={cards={{facing='back',base={value='Ace',suit='Spades'}},{facing='front',base={value='King',suit='Hearts'}}}}}
 local s=core.snapshot(g)
 eq(s.hand[1].hidden,true);eq(s.hand[1].rank,nil);eq(s.hand[1].suit,nil)
 eq(s.hand[2].rank,'King');eq(s.hand[2].suit,'Hearts')
 eq(s.hands_left,2);eq(s.discards_left,1);eq(s.blind.name,'The Fish')
end)
test('小丑稀有度随公开卡牌提供，盖住的牌仍不泄露',function()
 local hidden={facing='back',config={center={key='j_secret',set='Joker',rarity=3}},ability={set='Joker'}}
 local g={STATE=4,STATES={SHOP=4},GAME={},
  jokers={cards={{config={center={key='j_hologram',set='Joker',rarity=2}},ability={set='Joker'}}}},
  shop_jokers={cards={{config={center={key='j_baseball',set='Joker',rarity=3}},ability={set='Joker'},cost=6},hidden}}}
 local s=core.snapshot(g)
 eq(s.owned[1].rarity_label,'UNCOMMON')
 eq(s.shop[1].rarity_label,'RARE')
 eq(s.shop[2].hidden,true);eq(s.shop[2].rarity_label,nil)
end)
test('商店、出牌和选盲注各有独立的公开局面',function()
 local g={STATE=4,STATES={SHOP=4,SELECTING_HAND=1,BLIND_SELECT=7},GAME={round_resets={
  blind_choices={Small='bl_small',Big='bl_big',Boss='bl_ox'},
  blind_states={Small='Select',Big='Upcoming',Boss='Hide'},
  blind_tags={Small='tag_handy',Big='tag_coupon'}},blind_on_deck='Small'},
  P_BLINDS={bl_ox={secret='hidden'}}}
 eq(core.phase(g),'shop');g.STATE=1;eq(core.phase(g),'play')
 g.STATE=7;eq(core.phase(g),'blind_select')
 local s=core.snapshot(g,function(key)return '牌名:'..key end)
 eq(s.phase,'blind_select');eq(s.blind_on_deck,'Small');eq(#s.blind_options,2)
 eq(s.blind_options[1].skip_tag,'牌名:tag_handy');eq(s.blind_options[3],nil)
 eq(s.P_BLINDS,nil)
end)
test('开包时读取已亮出的选项和剩余选择，且不混入商店商品',function()
 local hidden={facing='back',config={center={key='j_secret',set='Joker'}},ability={set='Joker'}}
 local g={STATE=18,STATES={SHOP=5,BUFFOON_PACK=18},GAME={pack_choices=1,pack_size=3},
  pack_cards={cards={{config={center={key='j_visible',set='Joker'}},ability={set='Joker'}},hidden}},
  shop_jokers={cards={{config={center={key='j_shop',set='Joker'}},cost=4}}}}
 eq(core.phase(g),'pack')
 local s=core.snapshot(g,function(key)return '牌名:'..key end)
 eq(s.phase,'pack');eq(s.pack.type,'Buffoon');eq(s.pack.choices_left,1)
 eq(s.pack.size,3);eq(#s.pack.options,2);eq(s.pack.options[1].name,'牌名:j_visible')
 eq(s.pack.options[2].hidden,true);eq(s.pack.options[2].key,nil);eq(#s.shop,0)
 g.pack_cards.REMOVED=true
 eq(#core.snapshot(g).pack.options,0)
end)
test('Steamodded 开包状态：选盲注时开标签送的小丑包也认作开包',function()
 SMODS={OPENED_BOOSTER={config={center={key='p_buffoon_normal_1',kind='Buffoon'}}}}
 local g={STATE=999,STATES={SHOP=5,BLIND_SELECT=7,BUFFOON_PACK=18,SMODS_BOOSTER_OPENED=999},
  blind_select={},GAME={pack_choices=1,pack_size=2},
  pack_cards={cards={{config={center={key='j_popcorn',set='Joker'}},ability={set='Joker'}},
   {config={center={key='j_todo_list',set='Joker'}},ability={set='Joker'}}}}}
 eq(core.phase(g),'pack')
 local s=core.snapshot(g,function(key)return '牌名:'..key end)
 eq(s.phase,'pack');eq(s.pack.type,'Buffoon');eq(#s.pack.options,2)
 eq(s.pack.options[1].name,'牌名:j_popcorn')
 assert(core.scene_signature(g):find('^pack|'))
 SMODS.OPENED_BOOSTER.config.center.kind='Arcana'
 g.hand={cards={{base={suit='Hearts',value='King'},config={center={key='c_base',set='Default'}},ability={set='Default'}},
  {facing='back',base={suit='Spades',value='Ace'},config={center={key='c_base',set='Default'}},ability={set='Default'}}}}
 local arcana=core.snapshot(g)
 eq(arcana.pack.type,'Arcana');eq(#arcana.hand,2);eq(arcana.hand[2].suit,nil)
 SMODS=nil
end)
test('扑克牌名用点数加花色符号，模组新增的花色退回游戏文字',function()
 eq(core.playing_card_name({value='10',suit='Spades'}),'10♠')
 eq(core.playing_card_name({value='Ace',suit='Hearts'}),'A♥')
 eq(core.playing_card_name({value='Queen',suit='Diamonds'}),'Q♦')
 eq(core.playing_card_name({value='5',suit='Clubs'}),'5♣')
 eq(core.playing_card_name({value='5',suit='Stars'}),nil)
 eq(core.playing_card_name(nil),nil)
end)
test('读局面期间新登记的可动对象读完全部回收，原有对象不动',function()
 local list={}
 local function moveable(tag)
  local object={tag=tag}
  function object:remove() for i,v in ipairs(list) do if v==self then table.remove(list,i) break end end end
  list[#list+1]=object;return object
 end
 G={MOVEABLES=list}
 local shop=moveable('shop_jokers');local deck=moveable('deck')
 local before=core.moveable_count();eq(before,2)
 moveable('dynatext');moveable('spacer');moveable('spacer')
 local stuck=moveable('stuck');stuck.remove=function() end -- remove 不摘自己也不能死循环
 core.release_created(before)
 eq(#list,2);eq(list[1],shop);eq(list[2],deck)
 core.release_created(nil);eq(#list,2)
 G=nil;eq(core.moveable_count(),nil)
end)
test('提示节点里引用的真实游戏对象不被当成 DynaText 回收',function()
 -- 2026-11-03 对照局：刚买下的 Luchador 提示节点经 ref_table 指回卡牌本身，旧的回收顺着
 -- 所有字段一路走到商店界面，把 G.shop_jokers 当 DynaText remove 掉，下一次重掷游戏崩溃。
 G={UIT={T=1,C=2,O=3,R=4}}
 DynaText={};function DynaText.is(self,class) return class==DynaText and self.dynatext==true end
 local shop_jokers={cards={1,2},remove=function(self) self.cards=nil end,is=function() return false end}
 local card={children={shop={config={object=shop_jokers}}},area={config={object=shop_jokers}}}
 local removed=0
 local text_object={dynatext=true,is=DynaText.is,config={string={'Active!'}},remove=function()removed=removed+1 end}
 local ui={main={{{n=1,config={text='Sell to disable ',ref_table=card,ref_value='ability'}},
  {n=3,config={object=text_object,card=card}}}},info={},badges={card=card}}
 eq((core.game_text(ui)),'Sell to disable Active!')
 eq(#shop_jokers.cards,2);eq(removed,1)
 -- 结构里直接挂着的非 DynaText 对象（如 CardArea）也不回收。
 core.game_text({main={{{n=3,config={object=shop_jokers}}}}})
 eq(#shop_jokers.cards,2)
 G=nil;DynaText=nil
end)
test('游戏提示节点树压成文字，DynaText 读完即回收',function()
 G={UIT={T=1,C=2,O=3,R=4}}
 DynaText={};function DynaText.is(self,class) return class==DynaText end
 local removed=0
 local object={is=DynaText.is,config={string={'3',{string='张'}}},remove=function()removed=removed+1 end}
 local ui={main={
   {{n=1,config={text='将最多'}},{n=2,nodes={{n=3,config={object=object}}}}},
   {{n=1,config={text='选定卡牌转换为'}},{n=2,nodes={{n=1,config={text='梅花'}}}}}},
  info={{{{n=1,config={text='梅花：'}},{n=1,config={text='无特殊效果'}}}}}}
 local text,details=core.game_text(ui)
 eq(text,'将最多3张 选定卡牌转换为梅花');eq(details[1],'梅花：无特殊效果');eq(removed,1)
 -- 卡名也是 DynaText，虽然不读也必须回收，否则每次快照都在 G.MOVEABLES 里积累。
 local name_object={is=DynaText.is,config={string={'月亮'}},remove=function()removed=removed+1 end}
 core.game_text({main={},name={{n=3,config={object=name_object}}}})
 eq(removed,2)
 eq(core.game_text({main={}}),nil)
 -- Misprint 的随机滚动文字：数字候选给范围，其余取多数候选，不把整串候选拼出来。
 local numbers={};for i=0,23 do numbers[#numbers+1]=tostring(i) end
 local misprint={main={{{n=1,config={text='  +'}},
  {n=3,config={object={config={string=numbers,random_element=true}}}},
  {n=3,config={object={config={string={{string='rand()'},{string='#@7C'},' Mult ',' Mult ',' Mult '},random_element=true}}}}}}}
 eq((core.game_text(misprint)),'  +0~23 Mult ')
 -- 牌组说明是整棵节点树：按行节点分行。
 local tree={n=5,nodes={{n=4,nodes={{n=1,config={text='每回合'}},{n=1,config={text='+1弃牌'}}}},{n=4,nodes={{n=1,config={text='次数'}}}}}}
 eq(core.tree_text(tree),'每回合+1弃牌 次数')
 local card={generate_UIBox_ability_table=function()return ui end}
 eq((core.game_description(card)),'将最多3张 选定卡牌转换为梅花')
 eq(core.game_description({ability={}}),nil)
 eq(core.game_description({generate_UIBox_ability_table=function()error('x')end}),nil)
 G=nil;DynaText=nil
end)
test('所有阶段均读取持有道具卡，含可见效果与牌面修饰',function()
 local g={STATE=5,STATES={SHOP=5},GAME={},
  consumeables={config={card_limit=2},cards={{config={center={key='c_hex',set='Spectral'}},ability={set='Spectral'},edition={type='negative'},sell_cost=2}}}}
 local describe=function(key)return key=='c_hex' and '随机为一张小丑牌添加多彩，摧毁其他小丑牌' end
 local s=core.snapshot(g,function(key)return '牌名:'..key end,describe)
 eq(s.consumable_slots,2);eq(#s.consumables,1);eq(s.consumables[1].key,'c_hex')
 eq(s.consumables[1].name,'牌名:c_hex');eq(s.consumables[1].set,'Spectral')
 eq(s.consumables[1].description,'随机为一张小丑牌添加多彩，摧毁其他小丑牌')
 eq(s.consumables[1].edition,'negative');eq(s.consumables[1].sell_cost,2)
 g.STATE=1;eq(#core.snapshot(g).consumables,1)
end)
test('商店决策包含当前重掷价、利息规则和公开卡牌状态',function()
 local g={STATE=4,STATES={SHOP=4,SELECTING_HAND=2},GAME={dollars=35,interest_amount=1,interest_cap=25,rental_rate=3,
  bankrupt_at=-20,modifiers={money_per_hand=2,money_per_discard=1},
  current_round={reroll_cost=5,free_rerolls=0,hands_left=4,discards_left=3,
   current_hand={handname='Two Pair',chips=120,mult=8,hand_level='2'},most_played_poker_hand='Two Pair'},
  blind={name='The Psychic',loc_name='灵媒',chips=22000,dollars=5,loc_debuff_text='Must play 5 cards',
   config={blind={key='bl_psychic'}}}},
  jokers={config={card_limit=5},cards={{config={center={key='j_test',set='Joker'}},
   ability={set='Joker',mult=4,extra={chips=25},eternal=true,perishable=true,perish_tally=0},edition={type='foil'},sell_cost=3}}},
  shop_jokers={cards={{config={center={key='j_offer',set='Joker'}},ability={set='Joker',rental=true},cost=4}}}}
 local s=core.snapshot(g,function(key)return key end,function(key)return '效果:'..key end)
 eq(s.economy.reroll_cost,5);eq(s.economy.free_rerolls,0)
 eq(s.economy.interest_per_5,1);eq(s.economy.interest_cap,25);eq(s.economy.interest_now,5)
 eq(s.economy.interest_cap_balance,25);eq(s.economy.interest_max_reward,5)
 eq(s.economy.interest_if_round_ended_now,5)
 eq(s.economy.bankrupt_at,-20);eq(s.economy.money_per_hand,2);eq(s.economy.money_per_discard,1)
 eq(s.economy.rental_rate,3)
 eq(s.blind.key,'bl_psychic');eq(s.blind.name,'灵媒')
 eq(s.blind.name,'灵媒');eq(s.blind.reward,5);eq(s.blind.effect,'Must play 5 cards')
 eq(s.current_hand,nil)
 g.STATE=2
 local play=core.snapshot(g)
 eq(play.current_hand.name,'Two Pair');eq(play.current_hand.chips,120);eq(play.current_hand.mult,8)
 g.STATE=4
 eq(s.most_played_poker_hand,'Two Pair')
 eq(s.owned[1].edition,'foil');eq(s.owned[1].eternal,true)
 eq(s.owned[1].perishable,true);eq(s.owned[1].perish_tally,0)
 eq(s.owned[1].values.mult,4);eq(s.owned[1].values.extra_chips,25)
 eq(s.owned[1].description,'效果:j_test')
 eq(s.shop[1].rental,true);eq(s.shop[1].cost,4);eq(s.shop[1].description,'效果:j_offer')
 local dynamic=core.snapshot(g,nil,function()return '增加+?倍率',true end)
 eq(dynamic.owned[1].description_unresolved,true)
 g.GAME.modifiers.no_interest=true
 eq(core.snapshot(g).economy.interest_now,0)
end)
test('动态随机范围只提供公开边界，不泄露下一次结果',function()
 local g={STATE=4,STATES={SHOP=4},GAME={},shop_jokers={cards={
  {config={center={key='j_misprint',set='Joker'}},ability={set='Joker',extra={min=0,max=23}},cost=4}
 }}}
 local s=core.snapshot(g)
 eq(s.shop[1].values.extra_min,0);eq(s.shop[1].values.extra_max,23)
 eq(s.shop[1].values.next_random_mult,nil)
end)
test('已养成小丑的当前加成与成长步长分开提供',function()
 local function joker(key,ability)return {config={center={key=key,set='Joker'}},ability=ability} end
 local g={STATE=4,STATES={SHOP=4},GAME={},jokers={cards={
  joker('j_trousers',{set='Joker',extra=2,mult=4}),
  joker('j_runner',{set='Joker',extra={chips=45,chip_mod=15}}),
  joker('j_hologram',{set='Joker',extra=0.25,x_mult=1.5}),
  joker('j_stuntman',{set='Joker',extra={chip_mod=250,h_size=2}}),
  joker('j_unknown',{set='Joker',mult=4,extra=2}),
  joker('j_green_joker',{set='Joker',mult=3,extra={hand_add=1,discard_sub=1}}),
  joker('j_square',{set='Joker',extra={chips=12,chip_mod=4}}),
  joker('j_popcorn',{set='Joker',mult=16,extra=4}),
  joker('j_ramen',{set='Joker',x_mult=1.97,extra=0.01})}}}
 local owned=core.snapshot(g).owned
 eq(owned[1].current_bonus.kind,'add_mult');eq(owned[1].current_bonus.value,4)
 eq(owned[1].current_bonus.per_trigger,2)
 eq(owned[2].current_bonus.kind,'chips');eq(owned[2].current_bonus.value,45)
 eq(owned[2].current_bonus.per_trigger,15)
 eq(owned[3].current_bonus.kind,'x_mult');eq(owned[3].current_bonus.value,1.5)
 eq(owned[4].current_bonus,nil);eq(owned[4].values.extra_chip_mod,250)
 eq(owned[5].current_bonus,nil)
 eq(owned[6].current_bonus.value,3)
 eq(owned[7].current_bonus.value,12)
 eq(owned[8].current_bonus.value,16);eq(owned[8].current_bonus.per_trigger,-4)
 eq(owned[9].current_bonus.value,1.97);eq(owned[9].current_bonus.per_trigger,-0.01)
 local card={config={center={key='c_base',set='Default'}},ability={set='Default',perma_bonus=12,bonus=0},base={value='Ace',suit='Hearts'}}
 g.playing_cards={card};eq(core.snapshot(g).deck_catalog[1].values.perma_bonus,12)
end)
test('手牌上限和弃牌次数的小丑说明按游戏公开数值解析',function()
 local g={STATE=4,STATES={SHOP=4},GAME={},shop_jokers={cards={
  {config={center={key='j_juggler',set='Joker'}},ability={set='Joker',h_size=1},cost=4},
  {config={center={key='j_drunkard',set='Joker'}},ability={set='Joker',d_size=1},cost=4},
  {config={center={key='j_troubadour',set='Joker'}},ability={set='Joker',extra={h_size=2,h_plays=-1}},cost=6}}}}
 local labels={j_juggler='手牌上限+#1#',j_drunkard='弃牌次数+#1#',j_troubadour='手牌上限+#1#，出牌次数-#2#'}
 local s=core.snapshot(g,nil,function(key,_,card)
  local vars=core.tooltip_values(key,card)
  local unresolved=false
  local text=labels[key]:gsub('#(%d+)#',function(i)
   local value=vars and vars[tonumber(i)]
   if value==nil then unresolved=true;return '?' end
   return tostring(value)
  end)
  return text,unresolved
 end)
 eq(s.shop[1].description,'手牌上限+1');eq(s.shop[1].description_unresolved,nil)
 eq(s.shop[1].values.h_size,1)
 eq(s.shop[2].description,'弃牌次数+1');eq(s.shop[2].values.d_size,1)
 eq(s.shop[3].description,'手牌上限+2，出牌次数-1')
end)
test('常见固定效果占位符按牌型与数值解析',function()
 local localize=function(key,category)
  if category=='poker_hands' and key=='Pair' then return '对子' end
 end
 local jolly={ability={set='Joker',t_mult=8,type='Pair'}}
 local vars=core.tooltip_values('j_jolly',jolly,localize)
 eq(vars[1],8);eq(vars[2],'对子')
 eq(core.tooltip_values('j_credit_card',{ability={extra=20}})[1],20)
 local merry=core.tooltip_values('j_merry_andy',{ability={d_size=3,h_size=-1}})
 eq(merry[1],3);eq(merry[2],-1)
 local even=core.tooltip_values('j_even_steven',{ability={extra=4}})
 eq(even[1],4)
 local shop={STATE=4,STATES={SHOP=4},GAME={},shop_jokers={cards={{config={center={key='j_even_steven',set='Joker'}},
  ability={set='Joker',extra=4},cost=4}}}}
 local snap=core.snapshot(shop,nil,function(key,_,card)
  local vars=core.tooltip_values(key,card)
  return '偶数牌在计分时给予+'..tostring(vars and vars[1] or '?')..'倍率',vars==nil
 end)
 eq(snap.shop[1].description,'偶数牌在计分时给予+4倍率')
 eq(snap.shop[1].description_unresolved,nil)
end)
test('公开牌组与牌型可读，但不发送牌堆顺序或背面手牌身份',function()
 local visible={config={center={key='m_bonus',set='Enhanced'}},ability={set='Enhanced',effect='Bonus Card'},
  base={value='Ace',suit='Hearts'},seal='Gold',highlighted=true}
 local hidden={facing='back',base={value='King',suit='Spades'},config={center={key='c_secret'}}}
 local g={STATE=2,STATES={SELECTING_HAND=2},GAME={selected_back={effect={center={key='b_red'}}},
  stake=2,used_vouchers={v_seed_money=true},tags={{key='tag_handy'}},
  hands={['Two Pair']={visible=true,level=3,chips=30,mult=4,played=7,played_this_round=1},
   ['Flush Five']={visible=false,level=1,chips=160,mult=16,played=0}}},
  hand={config={card_limit=8},cards={visible,hidden}},
  deck={cards={{secret='next card'},{secret='second card'}}},discard={cards={{}}},
  playing_cards={hidden,visible}}
 hidden.area=g.deck
 local s=core.snapshot(g,function(key)return '牌名:'..key end)
 eq(s.hand_size,8);eq(s.hand[1].rank,'Ace');eq(s.hand[1].enhancement,'Bonus Card')
 eq(s.hand[1].seal,'Gold');eq(s.hand[1].selected,true)
 eq(s.hand[2].hidden,true);eq(s.hand[2].rank,nil)
 eq(s.deck_remaining,2);eq(s.discard_count,1);eq(s.deck,nil)
 eq(#s.deck_catalog,2);eq(s.deck_catalog[1].position,nil)
 local ranks={};for _,card in ipairs(s.deck_catalog)do if card.rank then ranks[card.rank]=card end end
 assert(ranks.King,'牌组总览应包含可在“查看牌组”中看到的背面手牌身份')
 eq(ranks.King.suit,'Spades');eq(ranks.Ace.seal,'Gold')
 eq(ranks.King.remaining_unplayed,true);eq(ranks.Ace.remaining_unplayed,false)
 eq(s.poker_hands['Two Pair'].level,3);eq(s.poker_hands['Two Pair'].played,7)
 eq(s.poker_hands['Two Pair'].played_this_round,1)
 eq(s.poker_hands['Flush Five'],nil)
 eq(s.back,'牌名:b_red');eq(s.stake,2)
 eq(s.vouchers[1].name,'牌名:v_seed_money');eq(s.tags[1].name,'牌名:tag_handy')
 local d=core.snapshot(g,nil,function()return '效果含?',true end)
 eq(d.vouchers[1].description_unresolved,true);eq(d.tags[1].description_unresolved,true)
 eq(d.back_description,'效果含?');eq(d.back_description_unresolved,true)
end)
test('可选盲注包含玩家能看到的目标、奖励和效果',function()
 local g={STATE=7,STATES={BLIND_SELECT=7},GAME={dollars=15,bankrupt_at=0,
  used_vouchers={v_directors_cut=true},round_resets={ante=2,blind_ante=3,boss_rerolled=false,
  blind_choices={Small='bl_small',Big='bl_big',Boss='bl_ox'},
  blind_states={Small='Select',Big='Upcoming',Boss='Hide'},blind_tags={Small='tag_handy'}},
  starting_params={ante_scaling=1}},P_BLINDS={bl_small={mult=1,dollars=3},bl_big={mult=1.5,dollars=4}}}
 local s=core.snapshot(g,function(key)return key end,function(key)return '效果:'..key end,
  {blind_amount=function(ante)eq(ante,3);return 800 end})
 eq(s.blind_options[1].chips,800);eq(s.blind_options[1].reward,3)
 eq(s.blind_options[1].effect,'效果:bl_small');eq(s.blind_options[1].skip_tag_effect,'效果:tag_handy')
 eq(s.blind_options[2].chips,1200);eq(s.blind_options[2].reward,4)
 eq(s.blind_options[3],nil)
 eq(s.boss_reroll_cost,10);eq(s.boss_reroll_available,true)
 g.GAME.round_resets.boss_rerolled=true
 eq(core.snapshot(g).boss_reroll_available,false)
 local d=core.snapshot(g,nil,function()return '效果含?',true end)
 eq(d.blind_options[1].effect_unresolved,true)
 eq(d.blind_options[1].skip_tag_effect_unresolved,true)
end)
test('比赛信息三栏在商店、开包、出牌和选盲注均可读取',function()
 local g={STATE=4,STATES={SHOP=4,BUFFOON_PACK=18,SELECTING_HAND=2,BLIND_SELECT=7},
  GAME={hands={['Two Pair']={visible=true,level=3,chips=35,mult=4,played=2}},
   used_vouchers={v_seed_money=true},round_resets={ante=2,blind_ante=2,
    blind_choices={Small='bl_small',Big='bl_big',Boss='bl_ox'},
    blind_states={Small='Select',Big='Upcoming',Boss='Hide'}}},
  P_BLINDS={bl_small={mult=1,dollars=3},bl_big={mult=1.5,dollars=4},bl_ox={mult=2,dollars=5}}}
 for _,state in ipairs({4,18,2,7}) do
  g.STATE=state
  local s=core.snapshot(g,function(key)return key end,nil,{blind_amount=function()return 800 end})
  eq(s.poker_hands['Two Pair'].level,3);eq(s.poker_hands['Two Pair'].played,2)
  eq(s.vouchers[1].key,'v_seed_money')
  eq(#s.blind_options,2);eq(s.blind_options[1].chips,800)
  eq(s.blind_options[2].chips,1200);eq(s.blind_options[3],nil)
 end
end)
test('开包候选牌生成后立即改变发布签名',function()
 local g={STATE=18,STATES={BUFFOON_PACK=18,SHOP=4},GAME={pack_choices=1},pack_cards={cards={}}}
 local before=core.scene_signature(g)
 g.pack_cards.cards[1]={config={center={key='j_first'}},ability={set='Joker'}}
 local after=core.scene_signature(g)
 assert(before~=after)
 g.pack_cards.cards[2]={config={center={key='j_second'}},ability={set='Joker'}}
 assert(after~=core.scene_signature(g))
 g.STATE=4
 assert(core.scene_signature(g)~=after)
end)
test('缺失游戏对象可以读取',function() local s=core.snapshot(nil);eq(s.phase,'other');eq(#s.shop,0) end)
test('语言缺失回退英语，替换变量安全',function()
 local tr=core.translator({['en-us']={title='Assistant',money='${value}'},zh_CN={title='助手'}})
 eq(tr('zh_CN','title'),'助手');eq(tr('ko','title'),'Assistant');eq(tr('zh_CN','money',{value='50%'}),'$50%')
end)
test('历史有限，牌局变更重置',function()
 local s=core.session(); local a={}; s:sync(a);s:add('user','测试');s:sync(a);eq(#s.messages,1)
 for i=1,80 do s:add('user',tostring(i)) end;eq(#s.messages,40)
 s:sync({});eq(#s.messages,0)
end)
print(n..' 项测试通过')
