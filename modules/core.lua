-- 无游戏副作用的布局、输入编辑和公开状态读取。
local M = {MAX_INPUT_BYTES = 2400}
local function boundary(s, p, direction)
 if direction < 0 then
  p = math.max(0,p-1)
  while p>0 and s:byte(p+1)>=128 and s:byte(p+1)<192 do p=p-1 end
 else
  p = math.min(#s,p+1)
  while p<#s and s:byte(p+1)>=128 and s:byte(p+1)<192 do p=p+1 end
 end
 return p
end
function M.fit_line(value, width, measure)
 if measure(value)<=width then return value,false end
 local ellipsis='…'
 if measure(ellipsis)>width then return '',true end
 local cursor=#value
 while cursor>0 do
  cursor=boundary(value,cursor,-1)
  local candidate=value:sub(1,cursor)..ellipsis
  if measure(candidate)<=width then return candidate,true end
 end
 return ellipsis,true
end
function M.editor(text)
 local e={text=text or '',cursor=#(text or ''),selected=false}
 function e:insert(value)
  value=value:gsub('[%c]',' ')
  local base=self.selected and '' or self.text
  local pos=self.selected and 0 or self.cursor
  local room=math.max(0,M.MAX_INPUT_BYTES-#base)
  local cut=math.min(#value,room)
  while cut>0 and cut<#value and value:byte(cut+1)>=128 and value:byte(cut+1)<192 do cut=cut-1 end
  value=value:sub(1,cut)
  self.text=base:sub(1,pos)..value..base:sub(pos+1); self.cursor=pos+#value; self.selected=false
 end
 function e:select_all() self.selected=true end
 function e:move(dir) self.selected=false;self.cursor=boundary(self.text,self.cursor,dir) end
 function e:home() self.selected=false;self.cursor=0 end
 function e:finish() self.selected=false;self.cursor=#self.text end
 function e:backspace()
  if self.selected then self:insert('');return end
  local p=boundary(self.text,self.cursor,-1)
  self.text=self.text:sub(1,p)..self.text:sub(self.cursor+1);self.cursor=p
 end
 function e:delete()
  if self.selected then self:insert('');return end
  self.text=self.text:sub(1,self.cursor)..self.text:sub(boundary(self.text,self.cursor,1)+1)
 end
 return e
end
function M.layout(w,h,width)
 local scale=math.max(0.65,math.min(1.5,h/900))
 local margin=16*scale
 local panelw=math.min(w-margin*2,math.max(390*scale,math.min(760*scale,(width or 520)*scale)))
 local y=math.min(h*0.28,260*scale)
 return {x=w-panelw-margin,y=y,w=panelw,h=h-y-margin,scale=scale,margin=margin}
end
function M.phase(g)
 g=g or {};local states=g.STATES or {}
 if g.STATE~=nil then
  -- Steamodded 开任何卡包都改用自己的 SMODS_BOOSTER_OPENED 状态，原版五种卡包状态不再出现。
  for _,key in ipairs({'SMODS_BOOSTER_OPENED','TAROT_PACK','PLANET_PACK','SPECTRAL_PACK','STANDARD_PACK','BUFFOON_PACK'}) do
   if g.STATE==states[key] then return 'pack' end
  end
 end
 if g.STATE~=nil and g.STATE==states.SHOP then return 'shop' end
 if g.blind_select or (g.STATE~=nil and g.STATE==states.BLIND_SELECT) then return 'blind_select' end
 if g.STATE~=nil and (g.STATE==states.SELECTING_HAND or g.STATE==states.DRAW_TO_HAND or g.STATE==states.HAND_PLAYED) then return 'play' end
 return 'other'
end
function M.shop_signature(g)
 if M.phase(g)~='shop' then return nil end
 local game=g.GAME or {};local current=game.current_round or {}
 local parts={tostring(game.dollars),tostring(current.reroll_cost)}
 for _,area in ipairs({'shop_jokers','shop_vouchers','shop_booster'}) do
  parts[#parts+1]=area
  for _,card in ipairs((g[area] or {}).cards or {}) do
   parts[#parts+1]=tostring(((card.config or {}).center or {}).key)..'@'..tostring(card.cost)
  end
 end
 return table.concat(parts,'|')
end
function M.scene_signature(g)
 g=g or {};local phase=M.phase(g);local game=g.GAME or {}
 local parts={phase}
 local cards
 if phase=='pack' then
  parts[#parts+1]=tostring(game.pack_choices)
  local area=g.pack_cards or {}
  cards=not area.REMOVED and area.cards or nil
 elseif phase=='play' then
  local round=game.current_round or {}
  parts[#parts+1]=tostring(game.chips)
  parts[#parts+1]=tostring(round.hands_left)
  parts[#parts+1]=tostring(round.discards_left)
  cards=(g.hand or {}).cards
 elseif phase=='blind_select' then
  local resets=game.round_resets or {}
  parts[#parts+1]=tostring(game.blind_on_deck)
  for _,slot in ipairs({'Small','Big','Boss'}) do
   parts[#parts+1]=tostring((resets.blind_choices or {})[slot])
   parts[#parts+1]=tostring((resets.blind_states or {})[slot])
  end
 end
 for _,card in ipairs(cards or {}) do
  local center=(card.config or {}).center or {};local base=card.base or {}
  parts[#parts+1]=table.concat({tostring(center.key),tostring(base.value),tostring(base.suit),
   tostring((card.ability or {}).effect),tostring((card.edition or {}).type),
   tostring(card.seal),tostring(card.facing),phase=='play' and tostring(card.highlighted) or ''},':')
 end
 return table.concat(parts,'|')
end
-- 只映射原版游戏提示中能直接从卡牌读取的变量；不调用会创建 UI 或修改状态的提示函数。
local tooltip_rules={
 j_trousers={kind='add_mult',current='mult',gain='extra',vars={'extra','poker_hands:Two Pair','mult'}},
 j_ride_the_bus={kind='add_mult',current='mult',gain='extra',vars={'extra','mult'}},
 j_red_card={kind='add_mult',current='mult',gain='extra',vars={'extra','mult'}},
 j_flash={kind='add_mult',current='mult',gain='extra',vars={'extra','mult'}},
 j_green_joker={kind='add_mult',current='mult',vars={'extra.hand_add','extra.discard_sub','mult'}},
 j_ceremonial={kind='add_mult',current='mult',vars={'mult'}},
 j_swashbuckler={kind='add_mult',current='mult',vars={'mult'}},
 j_popcorn={kind='add_mult',current='mult',gain='-extra',vars={'mult','extra'}},
 j_runner={kind='chips',current='extra.chips',gain='extra.chip_mod',vars={'extra.chips','extra.chip_mod'}},
 j_square={kind='chips',current='extra.chips',gain='extra.chip_mod',vars={'extra.chips','extra.chip_mod'}},
 j_wee={kind='chips',current='extra.chips',gain='extra.chip_mod',vars={'extra.chips','extra.chip_mod'}},
 j_ice_cream={kind='chips',current='extra.chips',gain='-extra.chip_mod',vars={'extra.chips','extra.chip_mod'}},
 j_constellation={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_hologram={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_vampire={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_lucky_cat={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_madness={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_campfire={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_glass={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_obelisk={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_throwback={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_hit_the_road={kind='x_mult',current='x_mult',gain='extra',vars={'extra','x_mult'}},
 j_ramen={kind='x_mult',current='x_mult',gain='-extra',vars={'x_mult','extra'}},
 j_stuntman={vars={'extra.chip_mod','extra.h_size'}},
 j_juggler={vars={'h_size'}},j_drunkard={vars={'d_size'}},
 j_troubadour={vars={'extra.h_size','-extra.h_plays'}},
 j_merry_andy={vars={'d_size','h_size'}},
 j_joker={vars={'mult'}},j_stencil={vars={'x_mult'}},
 j_half={vars={'extra.mult','extra.size'}},
 j_jolly={vars={'t_mult','poker_hands:@type'}},j_zany={vars={'t_mult','poker_hands:@type'}},
 j_mad={vars={'t_mult','poker_hands:@type'}},j_crazy={vars={'t_mult','poker_hands:@type'}},
 j_droll={vars={'t_mult','poker_hands:@type'}},
 j_sly={vars={'t_chips','poker_hands:@type'}},j_wily={vars={'t_chips','poker_hands:@type'}},
 j_clever={vars={'t_chips','poker_hands:@type'}},j_devious={vars={'t_chips','poker_hands:@type'}},
 j_crafty={vars={'t_chips','poker_hands:@type'}},
 j_photograph={vars={'extra'}},j_golden={vars={'extra'}},
}
-- 与原版 card.lua 的 loc_vars={self.ability.extra} 分支逐项核对；这里只映射直接取值的牌。
for _,key in ipairs({'j_chaos','j_credit_card','j_banner','j_fibonacci','j_scary_face',
 'j_delayed_grat','j_even_steven','j_odd_todd','j_astronomer','j_ticket','j_acrobat',
 'j_certificate','j_hanging_chad','j_rough_gem','j_arrowhead','j_onyx_agate',
 'j_flower_pot','j_seeing_double','j_matador','j_riff_raff','j_vagabond','j_baron',
 'j_gift','j_to_the_moon','j_baseball','j_trading','j_selzer','j_smiley',
 'j_shoot_the_moon','j_triboulet','j_perkeo'}) do
 tooltip_rules[key]=tooltip_rules[key] or {vars={'extra'}}
end
local function ability_value(ability,path)
 local negative=path:sub(1,1)=='-'
 if negative then path=path:sub(2) end
 local value=ability
 for part in path:gmatch('[^.]+') do
  if type(value)~='table' then return nil end
  value=value[part]
 end
 if negative then return type(value)=='number' and -value or nil end
 return value
end
function M.tooltip_values(key,card,localize_misc)
 local rule=tooltip_rules[key]
 if not rule or not rule.vars then return nil end
 local ability=(card or {}).ability or {};local vars={}
 for index,path in ipairs(rule.vars) do
  local category,loc_key=path:match('^([^:]+):(.+)$')
  if loc_key and loc_key:sub(1,1)=='@' then loc_key=ability_value(ability,loc_key:sub(2)) end
  local value=category and localize_misc and localize_misc(loc_key,category) or ability_value(ability,path)
  if value==nil then return nil end
  vars[index]=value
 end
 return vars
end
-- 游戏自己为悬停提示生成的节点树（Card:generate_UIBox_ability_table / generate_card_ui）：
-- main 是正文各行，info 是附带的子提示（强化、蜡封、版本的解释）。这是唯一覆盖全部
-- 卡类（小丑、塔罗、星球、幻灵、券、标签、卡包、增强牌）动态数值的来源；手写参数表
-- 只剩兜底。节点里的 DynaText 会登记进 G.MOVEABLES，读完文字必须 remove，否则每次
-- 快照都在泄漏可动对象。
local function node_text(node,parts)
 if type(node)~='table' then return end
 local config=node.config
 if type(config)=='table' then
  if type(config.text)=='string' then parts[#parts+1]=config.text end
  local object=config.object
  if type(object)=='table' then
   local strings=type(object.config)=='table' and object.config.string or nil
   if type(strings)=='string' then strings={strings} end
   local pieces={}
   for _,piece in ipairs(type(strings)=='table' and strings or {}) do
    if type(piece)=='string' then pieces[#pieces+1]=piece
    elseif type(piece)=='table' and type(piece.string)=='string' then pieces[#pieces+1]=piece.string end
   end
   if type(object.config)=='table' and object.config.random_element and #pieces>1 then
    -- 随机滚动文字（Misprint）：候选全是数字就给范围，否则取出现最多的那个候选。
    local low,high,numeric,counts,best,best_count=nil,nil,0,{},nil,0
    for _,piece in ipairs(pieces) do
     local number=tonumber(piece)
     if number then numeric=numeric+1;low=math.min(low or number,number);high=math.max(high or number,number) end
     counts[piece]=(counts[piece] or 0)+1
     if counts[piece]>best_count then best,best_count=piece,counts[piece] end
    end
    if numeric==#pieces then pieces={tostring(low)..'~'..tostring(high)} else pieces={best} end
   end
   for _,piece in ipairs(pieces) do parts[#parts+1]=piece end
  end
 end
 for _,child in ipairs(node.nodes or {}) do node_text(child,parts) end
end
local function rows_text(rows)
 local lines={}
 for _,row in ipairs(type(rows)=='table' and rows or {}) do
  local parts={}
  for _,node in ipairs(row) do node_text(node,parts) end
  local line=table.concat(parts)
  if line~='' then lines[#lines+1]=line end
 end
 return #lines>0 and table.concat(lines,' ') or nil
end
-- 读完文字后统一回收 DynaText：正文、名字、徽章里都有，每个只 remove 一次。
-- 只沿节点结构走（数组下标与这几个容器字段），不进 config：config 里的 ref_table 等指向真实
-- 卡牌，顺着走能到商店界面，曾把 G.shop_jokers 当成临时文字回收，下一次重掷游戏崩溃。
local UI_CONTAINERS={main=true,info=true,name=true,type=true,badges=true,nodes=true}
local function is_dynatext(object)
 if type(DynaText)~='table' or type(object.is)~='function' then return false end
 local ok,result=pcall(object.is,object,DynaText)
 return ok and result==true
end
local function scrub(value,visited,depth)
 if type(value)~='table' or visited[value] or depth>12 then return end
 visited[value]=true
 local config=value.config
 local object=type(config)=='table' and config.object or nil
 if type(object)=='table' and type(object.remove)=='function' and is_dynatext(object) then
  pcall(object.remove,object)
 end
 for key,child in pairs(value) do
  if type(child)=='table' and (type(key)=='number' or UI_CONTAINERS[key]) then
   scrub(child,visited,depth+1)
  end
 end
end
function M.game_text(ui)
 if type(ui)~='table' then return nil end
 local text=rows_text(ui.main)
 local details={}
 for _,box in ipairs(ui.info or {}) do
  local line=rows_text(box)
  if line then details[#details+1]=line end
 end
 scrub(ui,{},0)
 return text,details
end
-- 整棵节点树（如 Back:generate_UI 的返回值）：按行节点分行，其余文字顺序拼接。
function M.tree_text(root)
 local lines,current={},{}
 local row=type(G)=='table' and type(G.UIT)=='table' and G.UIT.R or nil
 local function walk(node)
  if type(node)~='table' then return end
  local starts_row=row~=nil and node.n==row
  local saved
  if starts_row then saved=current;current={} end
  local parts={}
  node_text({config=node.config},parts)
  for _,part in ipairs(parts) do current[#current+1]=part end
  for _,child in ipairs(node.nodes or {}) do walk(child) end
  if starts_row then
   local line=table.concat(current)
   if line~='' then lines[#lines+1]=line end
   current=saved
  end
 end
 walk(root)
 scrub(root,{},0)
 local rest=table.concat(current)
 if rest~='' then lines[#lines+1]=rest end
 return #lines>0 and table.concat(lines,' ') or nil
end
-- 2026-11-07：只回收 DynaText 时，悬停提示里还有对齐用的普通 Moveable 没人收，每次快照多 2 个，
-- 插件每秒读一次局面，半小时多出几千个可动对象，游戏每帧都要遍历它们，越玩越卡。
-- 读局面是同步的，期间新登记进 G.MOVEABLES 的只可能是提示生成的临时对象；
-- 读完把这之后新增的全部回收，原有对象（商店货架等）一个都不碰。
function M.moveable_count()
 return type(G)=='table' and type(G.MOVEABLES)=='table' and #G.MOVEABLES or nil
end
function M.release_created(before)
 local list=type(G)=='table' and G.MOVEABLES
 if type(list)~='table' or type(before)~='number' then return end
 for _=1,10000 do
  local count=#list
  if count<=before then return end
  local object=list[count]
  if type(object)=='table' and type(object.remove)=='function' then pcall(object.remove,object) end
  if #list==count then table.remove(list) end -- remove 没把自己摘出列表时手动摘，防止死循环
 end
end
function M.game_description(card)
 if type(card)~='table' or type(card.generate_UIBox_ability_table)~='function' then return nil end
 local ok,ui=pcall(card.generate_UIBox_ability_table,card)
 if not ok then return nil end
 return M.game_text(ui)
end
local rarity_labels={[1]='COMMON',[2]='UNCOMMON',[3]='RARE',[4]='LEGENDARY'}
local function visible_card(card,index,name,describe,catalog)
 if card.facing=='back' and not catalog then return {position=index,hidden=true} end
 local center=(card.config or {}).center or {};local ability=card.ability or {}
 local key=center.key or '?';local set=ability.set or center.set or ''
 local result={position=index,key=key,name=name and name(key,set,card) or key,set=set}
 if set=='Joker' and type(center.rarity)=='number' then
  result.rarity=center.rarity
  result.rarity_label=rarity_labels[center.rarity]
 end
 local base=card.base or {};if base.value then result.rank=base.value end
 if base.suit then result.suit=base.suit end
 if card.highlighted then result.selected=true end
 if ability.effect and ability.effect~='Base' then result.enhancement=ability.effect end
 if card.edition and card.edition.type then result.edition=card.edition.type end
 if card.seal then result.seal=card.seal end
 if card.debuff then result.debuffed=true end
 if ability.eternal then result.eternal=true end
 if ability.rental then result.rental=true end
 if ability.perishable then result.perishable=true end
 if type(ability.perish_tally)=='number' then result.perish_tally=ability.perish_tally end
 if card.sell_cost then result.sell_cost=card.sell_cost end
 local rule=tooltip_rules[key]
 if rule and rule.current then
  local current=ability_value(ability,rule.current)
  if type(current)=='number' then
   result.current_bonus={kind=rule.kind,value=current}
   local gain=rule.gain and ability_value(ability,rule.gain)
   if type(gain)=='number' then result.current_bonus.per_trigger=gain end
  end
 end
 local values={}
 for _,field in ipairs({'mult','t_mult','x_mult','chips','t_chips','h_mult','h_dollars','dollars','h_size','d_size','perma_bonus','bonus'}) do
  if type(ability[field])=='number' then values[field]=ability[field] end
 end
 if type(ability.extra)=='number' then values.extra=ability.extra
 elseif type(ability.extra)=='table' then
  for _,field in ipairs({'mult','chips','chip_mod','x_mult','Xmult','dollars','odds','bonus','rounds','discards','h_size','h_plays','hand_add','discard_sub','h_mod','increase','size','faces','d_remaining','s_mult','min','max'}) do
   if type(ability.extra[field])=='number' then values['extra_'..field]=ability.extra[field] end
  end
 end
 if next(values) then result.values=values end
 if describe then
  local description,unresolved,details=describe(key,set,card)
  result.description=description
  if unresolved then result.description_unresolved=true end
  if type(details)=='table' and #details>0 then result.details=details end
 end
 return result
end
function M.snapshot(g, name, describe, public)
 g=g or {};local game=g.GAME or {};local jokers=g.jokers or {};local states=g.STATES or {}
 local phase=M.phase(g);local shop=phase=='shop'
 local s={phase=phase,money=game.dollars or 0,
 ante=(game.round_resets or {}).ante or 0,round=game.round or 0,
 jokers=#(jokers.cards or {}),slots=(jokers.config or {}).card_limit or 0,shop={},owned={},hand={},blind_options={},consumables={},
 consumable_slots=((g.consumeables or {}).config or {}).card_limit or 0}
 local current=game.current_round or {}
 s.hands_left=current.hands_left or 0;s.discards_left=current.discards_left or 0
 s.hands_played=current.hands_played or 0;s.discards_used=current.discards_used or 0
 if phase=='play' then
  local shown=current.current_hand or {}
  s.current_hand={name=shown.handname,chips=shown.chips,mult=shown.mult,level=shown.hand_level}
 end
 s.most_played_poker_hand=current.most_played_poker_hand
 local modifiers=game.modifiers or {}
 s.economy={bankrupt_at=game.bankrupt_at or 0,
  interest_per_5=game.interest_amount,interest_cap=game.interest_cap,
  no_interest=modifiers.no_interest and true or false,
  money_per_hand=modifiers.no_extra_hand_money and 0 or modifiers.money_per_hand or 1,
  money_per_discard=modifiers.money_per_discard or 0,
  rental_rate=game.rental_rate}
 if type(game.interest_amount)=='number' and type(game.interest_cap)=='number' then
  s.economy.interest_now=not modifiers.no_interest and game.interest_amount*
   math.min(math.floor(math.max(0,s.money)/5),game.interest_cap/5) or 0
  s.economy.interest_cap_balance=game.interest_cap
  s.economy.interest_max_reward=modifiers.no_interest and 0 or game.interest_amount*game.interest_cap/5
  s.economy.interest_if_round_ended_now=s.economy.interest_now
 end
 if shop then
  s.economy.reroll_cost=current.reroll_cost
  s.economy.free_rerolls=current.free_rerolls or 0
 end
 local blind=game.blind or {};s.blind={name=blind.loc_name or blind.name or '',chips=blind.chips or 0,
  score=game.chips or 0,reward=blind.dollars,effect=blind.loc_debuff_text,
  disabled=blind.disabled and true or false,
  -- 计分器按 key 认 Boss（Flint、Psychic 等），名字和效果文字随语言变化。
  key=type(blind.config)=='table' and type(blind.config.blind)=='table' and blind.config.blind.key or nil}
 for index,card in ipairs(jokers.cards or {}) do
  s.owned[#s.owned+1]=visible_card(card,index,name,describe)
 end
 for index,card in ipairs((g.consumeables or {}).cards or {}) do
  s.consumables[#s.consumables+1]=visible_card(card,index,name,describe)
 end
 -- 塔罗包、幻灵包开包时也会发手牌供选目标，一并给出。
 if phase=='play' or phase=='pack' then
  for index,card in ipairs((g.hand or {}).cards or {}) do
   s.hand[#s.hand+1]=visible_card(card,index,name,describe)
  end
 end
 s.hand_size=((g.hand or {}).config or {}).card_limit
 if g.deck then s.deck_remaining=#(g.deck.cards or {}) end
 if g.discard then s.discard_count=#(g.discard.cards or {}) end
 s.deck_catalog={}
 for _,card in ipairs(g.playing_cards or {}) do
  -- “查看牌组”展示整副牌的卡面；这里不传牌所在区域与抽牌顺序。
  local entry=visible_card(card,nil,name,nil,true)
  entry.remaining_unplayed=not not ((g.deck and card.area==g.deck) or (card.ability or {}).wheel_flipped)
  s.deck_catalog[#s.deck_catalog+1]=entry
 end
 table.sort(s.deck_catalog,function(a,b)
  if a.hidden~=b.hidden then return a.hidden and true or false end
  local left=(a.suit or '')..':'..(a.rank or '')..':'..(a.key or '')..':'..(a.enhancement or '')
  local right=(b.suit or '')..':'..(b.rank or '')..':'..(b.key or '')..':'..(b.enhancement or '')
  return left<right
 end)
 s.poker_hands={}
 for key,hand in pairs(game.hands or {}) do
  if hand.visible then s.poker_hands[key]={level=hand.level,chips=hand.chips,mult=hand.mult,played=hand.played,
   played_this_round=hand.played_this_round} end
 end
 local back=game.selected_back and game.selected_back.effect and game.selected_back.effect.center
 local back_key=(back and back.key) or (type(game.selected_back_key)=='table' and game.selected_back_key.key)
 if back_key then
  s.back=name and name(back_key,'Back') or back_key
  if describe then
   local description,unresolved=describe(back_key,'Back')
   s.back_description=description
   if unresolved then s.back_description_unresolved=true end
  end
 end
 s.stake=game.stake
 s.vouchers={};for key,used in pairs(game.used_vouchers or {}) do
  if used then
   local entry={key=key,name=name and name(key,'Voucher') or key}
   if describe then
    local description,unresolved=describe(key,'Voucher')
    entry.description=description
    if unresolved then entry.description_unresolved=true end
   end
   s.vouchers[#s.vouchers+1]=entry
  end
 end
 table.sort(s.vouchers,function(a,b)return a.key<b.key end)
 s.tags={};for _,tag in ipairs(game.tags or {}) do
  if tag.key then
   local entry={key=tag.key,name=name and name(tag.key,'Tag') or tag.key}
   if describe then
    local description,unresolved=describe(tag.key,'Tag')
    entry.description=description
    if unresolved then entry.description_unresolved=true end
   end
   s.tags[#s.tags+1]=entry
  end
 end
 if phase=='pack' then
  local kind
  for state,label in pairs({TAROT_PACK='Arcana',PLANET_PACK='Celestial',SPECTRAL_PACK='Spectral',STANDARD_PACK='Standard',BUFFOON_PACK='Buffoon'}) do
   if g.STATE==states[state] then kind=label;break end
  end
  if not kind then
   -- Steamodded 下卡包类型记在正在打开的卡包上，kind 与原版类别同名（Arcana、Buffoon 等）。
   local smods=rawget(_G,'SMODS')
   local opened=type(smods)=='table' and smods.OPENED_BOOSTER or nil
   local center=type(opened)=='table' and opened.config and opened.config.center or nil
   if type(center)=='table' and type(center.kind)=='string' then kind=center.kind end
  end
  s.pack={type=kind or '',choices_left=game.pack_choices or 0,size=game.pack_size or 0,options={}}
  local area=g.pack_cards or {}
  if not area.REMOVED then
   for index,card in ipairs(area.cards or {}) do
    s.pack.options[#s.pack.options+1]=visible_card(card,index,name,describe)
   end
  end
 end
 if shop then
  for _,area in ipairs({'shop_jokers','shop_vouchers','shop_booster'}) do
   for _,card in ipairs((g[area] or {}).cards or {}) do
    local item=visible_card(card,nil,name,describe)
    item.cost=card.cost or 0
    s.shop[#s.shop+1]=item
   end
  end
 end
 local resets=game.round_resets or {}
 s.blind_on_deck=game.blind_on_deck
 if phase=='blind_select' then
  local vouchers=game.used_vouchers or {}
  if vouchers.v_retcon or vouchers.v_directors_cut then
   s.boss_reroll_cost=10
   s.boss_reroll_available=(s.money-(game.bankrupt_at or 0)>=10) and
    (vouchers.v_retcon or not resets.boss_rerolled) and true or false
  end
 end
 for _,slot in ipairs({'Small','Big','Boss'}) do
   local key=(resets.blind_choices or {})[slot]
   if key and (resets.blind_states or {})[slot]~='Hide' then
    local tag_key=(resets.blind_tags or {})[slot]
    local proto=(g.P_BLINDS or {})[key] or {}
    local option={slot=slot,key=key,
     name=name and name(key,'Blind') or key,state=(resets.blind_states or {})[slot] or '',
     reward=modifiers.no_blind_reward and modifiers.no_blind_reward[slot] and 0 or proto.dollars,
     skip_tag=tag_key and (name and name(tag_key,'Tag') or tag_key) or nil}
    if describe then
     local effect,unresolved=describe(key,'Blind')
     option.effect=effect
     if unresolved then option.effect_unresolved=true end
     if tag_key then
      local tag_effect,tag_unresolved=describe(tag_key,'Tag')
      option.skip_tag_effect=tag_effect
      if tag_unresolved then option.skip_tag_effect_unresolved=true end
     end
    end
    local amount=public and public.blind_amount and public.blind_amount(resets.blind_ante or resets.ante)
    if type(amount)=='number' and type(proto.mult)=='number' then
     option.chips=math.floor(amount*proto.mult*((game.starting_params or {}).ante_scaling or 1))
    end
    s.blind_options[#s.blind_options+1]=option
   end
 end
 return s
end
-- 扑克牌名统一写成「点数 + 花色符号」（10♠、A♥），比「10 · 黑桃」好读，各语言通用。
-- 模组新增的花色没有通用符号，返回 nil，由调用方退回游戏自己的文字。
local SUIT_SYMBOLS={Spades='♠',Hearts='♥',Diamonds='♦',Clubs='♣'}
local RANK_SHORT={Ace='A',King='K',Queen='Q',Jack='J'}
function M.playing_card_name(base)
 if type(base)~='table' then return nil end
 local symbol=SUIT_SYMBOLS[base.suit]
 local rank=RANK_SHORT[base.value] or (type(base.value)=='string' and base.value:match('^%d+$') and base.value)
 if symbol and rank then return rank..symbol end
 return nil
end
function M.translator(languages)
 return function(locale,key,vars)
  local value=(languages[locale] or {})[key] or (languages['en-us'] or {})[key] or key
  return (value:gsub('{([%w_]+)}',function(k) return tostring((vars or {})[k] or '{'..k..'}') end))
 end
end
function M.session()
 local s={messages={}}
 function s:sync(run)
  if self.run~=run then self.run=run;self.messages={};return true end
  return false
 end
 function s:add(role,text,source)
  self.messages[#self.messages+1]={role=role,text=text,source=source}
  if #self.messages>40 then table.remove(self.messages,1) end
 end
 return s
end
return M
