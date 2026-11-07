-- 原生覆盖层：事件先判断归属，再交还游戏。
return function(core, tr, model)
 local P={open=false,focused=false,width=520,scroll=0,details_scroll=0,editor=core.editor(),session=core.session(),fonts={},composition='',model=model}
 local colours={bg={0.065,0.105,0.115,0.98},well={0.10,0.15,0.16,1},gold={0.89,0.69,0.31,1},text={0.96,0.94,0.86,1},muted={0.63,0.72,0.70,1},red={0.89,0.25,0.24,1}}
 local function inside(x,y,r) return x>=r.x and x<=r.x+r.w and y>=r.y and y<=r.y+r.h end
 local function now()return love.timer.getTime()end
 function P:locale()return (G and G.SETTINGS and G.SETTINGS.language) or 'en-us' end
 function P:t(key,vars)return tr(self:locale(),key,vars)end
 function P:visible()
  local w,h=love.graphics.getDimensions()
  return w>=640 and h>=480 and G and G.STAGES and G.STAGE==G.STAGES.RUN and not G.OVERLAY_MENU and not G.screenwipe
 end
 function P:rect()local w,h=love.graphics.getDimensions();return core.layout(w,h,self.width)end
 function P:entry()
  local w,h=love.graphics.getDimensions();local s=self:rect().scale
  return {x=w-180*s,y=18*s,w=164*s,h=48*s}
 end
 function P:regions()
  local r=self:rect();local s=r.scale;local pad=18*s
  return r,{x=r.x+pad,y=r.y+r.h-80*s,w=r.w-2*pad,h=64*s},
   {x=r.x+r.w-92*s,y=r.y+r.h-72*s,w=66*s,h=48*s},
   {x=r.x+r.w-85*s,y=r.y+14*s,w=68*s,h=30*s}
 end
 function P:details_regions()
  local r,input=self:regions();local s=r.scale
  local summary={x=r.x+18*s,y=r.y+110*s,w=r.w-36*s,h=32*s}
  local popup={x=summary.x,y=summary.y+summary.h,w=summary.w,
   h=math.min(220*s,math.max(0,input.y-summary.y-summary.h-8*s))}
  return summary,popup
 end
 function P:settings_regions()
  local r,_,_,close=self:regions();local s=r.scale
  local gear={x=close.x-48*s,y=close.y,w=40*s,h=close.h}
  local card={x=r.x+18*s,y=r.y+132*s,w=r.w-36*s,h=315*s}
  -- 模型、强度档位、目标是否可选都由桥接的 capabilities 决定；这里的默认值只在桥接未应答时用。
  local models=self.capabilities or P.default_models
  local selected=self.remote_settings and self.remote_settings.model or models[1].id
  local levels=P.default_models[1].efforts
  for _,item in ipairs(models)do if item.id==selected then levels=item.efforts end end
  local model_rects={};local gap=6*s;local inner=card.w-24*s
  local modelw=(inner-(#models-1)*gap)/#models
  for i,item in ipairs(models)do model_rects[i]={x=card.x+12*s+(i-1)*(modelw+gap),y=card.y+43*s,w=modelw,h=38*s,id=item.id,name=item.name or item.id} end
  local effort_rects={};local effortw=(inner-(#levels-1)*gap)/#levels
  for i,id in ipairs(levels)do effort_rects[i]={x=card.x+12*s+(i-1)*(effortw+gap),y=card.y+116*s,w=effortw,h=36*s,id=id} end
  local modew=(inner-gap)/2
  local goals={}
  for i,goal in ipairs(self.goal_options or P.default_goals)do
   goals[i]={x=card.x+12*s+(i-1)*(modew+gap),y=card.y+189*s,w=modew,h=40*s,id=goal.id,enabled=goal.enabled~=false}
  end
  return {gear=gear,card=card,models=model_rects,efforts=effort_rects,goals=goals,
   inside={x=card.x+12*s,y=card.y+259*s,w=modew,h=40*s},
   outside={x=card.x+12*s+modew+gap,y=card.y+259*s,w=modew,h=40*s}}
 end
 function P:focus(value)
  if self.focused==value then return end
  self.focused=value;self.composition=''
  if value then
   self.oldrepeat=love.keyboard.hasKeyRepeat();self.oldtext=love.keyboard.hasTextInput and love.keyboard.hasTextInput() or false
   local _,input=self:regions();love.keyboard.setTextInput(true,input.x,input.y,input.w,input.h);love.keyboard.setKeyRepeat(true)
  else
   love.keyboard.setTextInput(self.oldtext or false);love.keyboard.setKeyRepeat(self.oldrepeat or false)
  end
 end
 function P:seed_suggestion()
  if not self:visible() or self.composition~='' then return end
  local phase=core.phase(G);local locale=self:locale()
  if phase~=self.suggested_phase or locale~=self.suggested_locale then
   if phase~=self.suggested_phase then self.prompt_used=false end
   if not self.prompt_used and (self.suggested or self.editor.text=='') then
    self.editor=core.editor(self:t('suggest_'..phase));self.suggested=true
   end
   self.suggested_phase=phase;self.suggested_locale=locale
  end
 end
 P.default_models={{id='claude-opus-5-5',name='Opus 5.5',efforts={'low','medium','high','xhigh','max'}},
  {id='claude-fable-5-1',name='Fable 5.1',efforts={'low','medium','high','xhigh','max'}}}
 P.default_goals={{id='clear',enabled=true},{id='endless',enabled=false}}
 function P:model_display_name(id)
  for _,item in ipairs(self.capabilities or P.default_models)do if item.id==id then return item.name or id end end
  return id
 end
 -- 聊天区要画的条目：历史消息，加上回答中的「正在思考」气泡（带跳动的省略号和已等待秒数，免得玩家以为卡死）。
 function P:chat_content()
  local content={}
  if #self.session.messages==0 then content[1]={text=self:t('welcome'),role='assistant'}
  else for i,m in ipairs(self.session.messages)do content[i]=m end end
  if self.pending or self.remote_pending then
   local started=self.pending and self.pending.started or self.remote_pending_since or now()
   local dots=('.'):rep(1+math.floor(now()*2)%3)
   content[#content+1]={role='assistant',thinking=true,
    text=self:t('thinking'):gsub('…$','')..dots..'  '..math.floor(math.max(0,now()-started))..'s'}
  end
  return content
 end
 function P:bridge_active()return self.model and self.model.is_bridge and self.model:is_bridge()end
 function P:change_settings(changes,after)
  if not self:bridge_active() then return false,'unsupported' end
  return self.model:set_settings(changes,function(ok,value)
   if ok and type(value)=='table' and type(value.settings)=='table' then
    self.remote_settings=value.settings;self.settings_error=nil
   else self.settings_error=value end
   if after then after(ok,value) end
  end)
 end
 function P:show_outside()
  local function restore_inside(reason)
   self.settings_error=reason
   self:change_settings({display_mode='inside'},function()self.settings_error=reason end)
  end
  return self:change_settings({display_mode='outside'},function(ok)
   if not ok then return end
   local started=self.model:open_companion(function(opened,value)
   if not opened then
    restore_inside(value or 'network');return
   end
    if value.kind=='browser' then
     local ok,result=pcall(love.system.openURL,'http://127.0.0.1:8765/')
     if not ok or not result then
      restore_inside('companion_unavailable');return
     end
    end
    self.mode='outside';self.open=false;self.settings_open=false;self.details_open=false;self:focus(false)
   end)
   if not started then restore_inside('network') end
  end)
 end
 function P:show_inside()
  return self:change_settings({display_mode='inside'},function(ok)
   self.mode='inside';self.open=true;self.settings_open=false
   self:seed_suggestion()
   if not ok then self.bridge_connected=false end
  end)
 end
 function P:toggle()
  if not self.open and self.mode=='outside' then
   local started=self:show_inside()
   if not started then self.mode='inside';self.open=true;self.bridge_connected=false end
   return
  end
  self.open=not self.open
  if self.open then self:seed_suggestion()
  else self:focus(false);self.resizing=nil;self.settings_open=false;self.details_open=false end
 end
 function P:sync_bridge()
  if not self:bridge_active() or not self:visible() then return end
  local run_id=tostring(G.GAME)
  if self.run_id~=run_id then
   self.run_id=run_id;self.next_publish=0;self.next_poll=0;self.polling=false
   self.last_shop_signature=nil;self.last_scene_signature=nil;self.snapshot_revision=0
  end
  local shop_signature=core.shop_signature(G)
  local scene_signature=core.scene_signature(G)
  if now()>=(self.next_publish or 0) or shop_signature~=self.last_shop_signature or
   scene_signature~=self.last_scene_signature then
   self.next_publish=now()+1
   self.last_shop_signature=shop_signature
   self.last_scene_signature=scene_signature
   self.snapshot_revision=(self.snapshot_revision or 0)+1
   local snapshot=self:read_snapshot();snapshot.snapshot_revision=self.snapshot_revision
   self.model:publish(run_id,snapshot,self:locale(),function(ok)
    if not ok then self.bridge_connected=false end
   end)
  end
  if now()>=(self.next_poll or 0) and not self.polling then
   self.next_poll=now()+1;self.polling=true
   local started=self.model:poll(function(ok,state)
    self.polling=false
    if not ok then self.bridge_connected=false;return end
    if type(state)~='table' or state.run_id~=self.run_id then return end
    self.bridge_connected=state.connected
    if type(state.messages)=='table' then
     local messages={}
     for i,item in ipairs(state.messages)do
      messages[i]={role=item.role,source=item.source,
       text=item.source=='error' and self:t('error_'..tostring(item.text),{seconds=315}) or tostring(item.text or '')}
     end
     self.session.messages=messages
    end
    if state.pending and not self.remote_pending then self.remote_pending_since=now() end
    self.remote_pending=state.pending
    if type(state.prompt_used)=='boolean' and type(state.snapshot)=='table' and state.snapshot.phase==core.phase(G) then
     self.prompt_used=state.prompt_used
     if self.prompt_used and self.suggested then self.editor=core.editor();self.suggested=false end
    end
    if type(state.settings)=='table' then
     local old=self.mode
     self.remote_settings=state.settings;self.mode=state.settings.display_mode
     if old=='outside' and self.mode=='inside' then self.open=true;self:seed_suggestion() end
    end
    if self.pending and not state.pending then self.pending=nil end
   end)
   if not started then self.polling=false;self.bridge_connected=false end
  end
  if not self.capabilities_loading and not self.capabilities and self.model.capabilities and now()>=(self.next_capabilities or 0) then
   self.capabilities_loading=true;self.next_capabilities=now()+5
   local started=self.model:capabilities(function(ok,value)
    self.capabilities_loading=false
    if ok and type(value)=='table' then self.capabilities=value.models;self.goal_options=value.goals end
   end)
   if not started then self.capabilities_loading=false end
  end
 end
 function P:submit(text)
  if self.composition~='' or now()<(self.ime_until or 0) then return end
  text=text or self.editor.text
  if not text:find('%S') then return end
  if self.pending or self.remote_pending then return end
  local history={};for i,m in ipairs(self.session.messages)do history[i]=m end
  self.session:add('user',text)
  self.editor=core.editor();self.suggested=false;self.prompt_used=true;self.scroll=0
  if not self.model then self.session:add('assistant',self:t('unavailable'),'error');return end
  local run=self.session.run;local id=(self.request_id or 0)+1;self.request_id=id
  local config=self.model:configuration()
  self.pending={id=id,run=run,started=now(),timeout=config and config.timeout_seconds or 45}
  local snapshot=self:read_snapshot()
  if self:bridge_active() then
   self.snapshot_revision=(self.snapshot_revision or 0)+1
   snapshot.snapshot_revision=self.snapshot_revision
   self.last_shop_signature=core.shop_signature(G)
  end
  local started,err=self.model:ask(text,snapshot,self:locale(),history,function(ok,value)
   if not self.pending or self.pending.id~=id or self.session.run~=run then return end
   self.pending=nil
   if not ok and value=='scene_loading' then self.editor=core.editor(text) end
   self.session:add('assistant',ok and value or self:t('error_'..value),ok and 'model' or 'error')
   self.scroll=0
  end,self.run_id)
  if not started then
   self.pending=nil
   self.session:add('assistant',self:t('error_'..(err or 'network')),'error')
  end
 end
 function P:update()
  if self.session:sync(G and G.GAME) then self.editor=core.editor();self.suggested=false;self.suggested_phase=nil;self.prompt_used=false;self.scroll=0;self.pending=nil;self.remote_pending=nil;self:focus(false) end
  self:seed_suggestion()
  self:sync_bridge()
  if self.pending and now()-self.pending.started>self.pending.timeout then
   local seconds=self.pending.timeout
   self.pending=nil;self.session:add('assistant',self:t('error_timeout',{seconds=seconds}),'error')
  end
  if self.model and now()>=(self.status_check_at or 0) then
   local config,err=self.model:configuration();self.model_name=config and (self.remote_settings and (self:model_display_name(self.remote_settings.model)..' · '..self:t('effort_'..self.remote_settings.effort)) or config.model):sub(1,36) or nil
   self.config_error=err;self.status_check_at=now()+2
  end
  local visible=self:visible()
  if not visible then self:focus(false);self.resizing=nil;self.details_open=false end
  if G and G.CONTROLLER and G.CONTROLLER.locks then
   G.CONTROLLER.locks.balatro_assistant=(visible and self.open and self.focused) or nil
  end
 end
 function P:mousepressed(x,y,button)
  if not self:visible() then return false end
  if not self.open then if inside(x,y,self:entry()) then if button==1 then self:toggle() end;return true end;return false end
  local r,input,send,close=self:regions();local settings=self:settings_regions()
  if not inside(x,y,r) then
   if self.settings_open then self.settings_open=false;return true end
   self:focus(false);return false
  end
  if button~=1 then return true end
  local _,details=self:details_regions()
  if self.details_open and inside(x,y,details) and not self.settings_open then return true end
  if inside(x,y,close) then self:toggle()
  elseif inside(x,y,settings.gear) and self:bridge_active() then self.settings_open=not self.settings_open;self:focus(false)
  elseif self.settings_open then
   local selected=self.remote_settings and self.remote_settings.effort or 'high'
   local handled=false
   for _,item in ipairs(settings.models)do
    if inside(x,y,item) then
     local levels=P.default_models[1].efforts
     for _,model in ipairs(self.capabilities or P.default_models)do if model.id==item.id then levels=model.efforts end end
     local supported=false;for _,level in ipairs(levels)do if level==selected then supported=true end end
     self:change_settings({model=item.id,effort=supported and selected or levels[1]});handled=true;break
    end
   end
   if not handled then for _,item in ipairs(settings.efforts)do
    if inside(x,y,item) then self:change_settings({effort=item.id});handled=true;break end
   end end
   if not handled then for _,item in ipairs(settings.goals)do
    if inside(x,y,item) then if item.enabled then self:change_settings({play_goal=item.id}) end;handled=true;break end
   end end
   if not handled and inside(x,y,settings.inside) then self:show_inside();handled=true end
   if not handled and inside(x,y,settings.outside) then self:show_outside();handled=true end
   if not handled then self.settings_open=false end
  elseif x<r.x+10*r.scale then self.resizing={x=x,width=r.w/r.scale,scale=r.scale};self:focus(false)
  elseif inside(x,y,send) then self:submit()
  elseif inside(x,y,input) then self:focus(true)
  else self:focus(false) end
  return true
 end
 function P:mousemoved(x,y)
  if self.resizing then
   local drag=self.resizing
   self.width=math.max(390,math.min(760,drag.width+(drag.x-x)/drag.scale));return true
  end
  if not self.open or self.settings_open or not self.details_truncated then self.details_open=false;return end
  local summary,popup=self:details_regions()
  if inside(x,y,summary) then self.details_open=true
  elseif self.details_open and not inside(x,y,popup) then self.details_open=false;self.details_scroll=0 end
 end
 function P:mousereleased()self.resizing=nil end
 function P:keypressed(key)
  if not self:visible() then return false end
  -- macOS 的 Fn+F8 会向 LÖVE 发送 f8；Fn 本身不是 LÖVE 可读取的修饰键。
  if key=='f8' then self:toggle();return true end
  if key=='escape' and self.settings_open then self.settings_open=false;return true end
  if not self.focused then return false end
  if self.composition~='' then return true end
  local modifier=love.keyboard.isDown('lctrl','rctrl','lgui','rgui')
  if key=='escape' then self:focus(false)
  elseif key=='return' or key=='kpenter' then self:submit()
  elseif key=='backspace' then self.editor:backspace();self.suggested=false
  elseif key=='delete' then self.editor:delete();self.suggested=false
  elseif key=='left' then self.editor:move(-1)
  elseif key=='right' then self.editor:move(1)
  elseif key=='home' then self.editor:home()
  elseif key=='end' then self.editor:finish()
  elseif modifier and key=='a' then self.editor:select_all()
  elseif modifier and key=='v' then self.editor:insert(love.system.getClipboardText());self.suggested=false end
  return true
 end
 function P:textinput(text)
  if not self.focused or not self:visible() then return false end
  if self.composition~='' then self.ime_until=now()+0.12 end
  self.composition='';self.editor:insert(text);self.suggested=false;return true
 end
 function P:textedited(text)
  if not self.focused or not self:visible() then return false end
  self.composition=text;self.ime_until=now()+0.12;return true
 end
 function P:wheelmoved(_,dy)
  local x,y=love.mouse.getPosition()
  if self:visible() and self.open and self.details_open then
   local _,popup=self:details_regions()
   if inside(x,y,popup) then
    self.details_scroll=math.max(0,math.min(self.details_maxscroll or 0,self.details_scroll-dy*42*self:rect().scale))
    return true
   end
  end
  if self:visible() and self.open and inside(x,y,self:rect()) then
   self.scroll=math.max(0,math.min(self.maxscroll or 0,self.scroll+dy*42*self:rect().scale));return true
  end
  return false
 end
 function P:font(size)
  local file=G and G.LANG and G.LANG.font and G.LANG.font.file
  local key=tostring(file)..':'..size
  if not self.fonts[key] then
   local ok,f=pcall(love.graphics.newFont,file or size,file and size or nil)
   f=ok and f or love.graphics.newFont(size)
   -- 英语等语言的像素字体没有 ♠♥♦♣，借游戏自带的 GoNoto 字体补字形。中日韩字体本身就有，不额外加载。
   -- GoNoto 有 14 MB，文件只读一次，各字号共用；任何一步失败都照常用原字体。
   local has_ok,has=pcall(function() return f:hasGlyphs('♠♥♦♣') end)
   if not (has_ok and has) and f.setFallbacks then
    if self.fallback_data==nil then
     local data_ok,data=pcall(love.filesystem.newFileData,'resources/fonts/GoNotoCurrent-Bold.ttf')
     self.fallback_data=data_ok and data or false
    end
    if self.fallback_data then
     local fb_ok,fallback=pcall(function() return love.graphics.newFont(love.font.newRasterizer(self.fallback_data,size)) end)
     if fb_ok and fallback then pcall(f.setFallbacks,f,fallback) end
    end
   end
   self.fonts[key]=f
  end
  return self.fonts[key]
 end
 function P:read_snapshot()
  local before=core.moveable_count()
  local public={}
  if type(get_blind_amount)=='function' then
   public.blind_amount=function(ante)
    local ok,amount=pcall(get_blind_amount,ante)
    return ok and amount or nil
   end
  end
  local snapshot=core.snapshot(G,function(key,set,card)
   if set=='Default' then
    local base=card and card.base or {}
    local label=core.playing_card_name(base)
    if label then return label end
    local misc=G.localization and G.localization.misc or {}
    local rank=(misc.ranks or {})[base.value]
    local suit=(misc.suits_plural or {})[base.suit]
    if rank and suit then return rank..' · '..suit end
   end
   local descriptions=G.localization and G.localization.descriptions
  local lookup=set=='Booster' and key:gsub('_%d+$','') or key
   local lookup_set=set=='Booster' and 'Other' or (set or 'Joker')
   local item=descriptions and descriptions[lookup_set] and descriptions[lookup_set][lookup]
   local name=item and item.name
   if type(name)=='table' then name=table.concat(name,' ') end
   return type(name)=='string' and name:gsub('{[^}]*}','') or key
  end,function(key,set,card)
  -- 先要游戏自己生成的悬停文字：它为每种卡类算好了全部动态数值。
  local game_text,game_details=core.game_description(card)
  if set=='Back' then
   local back=G.GAME and G.GAME.selected_back
   if type(back)=='table' and type(back.generate_UI)=='function' then
    local ok,root=pcall(back.generate_UI,back)
    if ok then game_text=core.tree_text(root) end
   end
  end
  if not game_text and (set=='Voucher' or set=='Tag') and type(generate_card_ui)=='function' then
   local center=set=='Tag' and (G.P_TAGS or {})[key] or (G.P_CENTERS or {})[key]
   if center then
    local ok,ui=pcall(generate_card_ui,center,nil,nil,set)
    if ok then game_text,game_details=core.game_text(ui) end
   end
  end
  if not game_text and set=='Blind' and type(localize)=='function' then
   local proto=(G.P_BLINDS or {})[key]
   if proto then
    -- 与 Blind:set_text 同源：The Ox 填最常打牌型，SMODS 盲注走自己的 loc_vars。
    local target={type='raw_descriptions',key=key,set='Blind',vars=proto.vars or {}}
    if proto.name=='The Ox' then
     local hand=((G.GAME or {}).current_round or {}).most_played_poker_hand
     if hand then target.vars={localize(hand,'poker_hands')} end
    end
    if type(proto.loc_vars)=='function' then
     local ok,res=pcall(proto.loc_vars,proto)
     res=ok and type(res)=='table' and res or {}
     target.vars=res.vars or target.vars;target.key=res.key or target.key;target.set=res.set or target.set
    end
    local ok,lines=pcall(localize,target)
    if ok then
     if type(lines)=='string' then lines={lines} end
     if type(lines)=='table' and #lines>0 then game_text=table.concat(lines,' ') end
    end
   end
  end
  if game_text and not game_text:find('ERROR',1,true) then return game_text,nil,game_details end
  local descriptions=G.localization and G.localization.descriptions
  local lookup=set=='Booster' and key:gsub('_%d+$','') or key
   local lookup_set=set=='Booster' and 'Other' or set
   local item=descriptions and descriptions[lookup_set] and descriptions[lookup_set][lookup]
   if not item or type(item.text)~='table' then return nil end
   local vars=set=='Joker' and core.tooltip_values(key,card,function(value,category)
    local misc=G.localization and G.localization.misc or {}
    return (misc[category] or {})[value]
   end) or nil
   local lines={};local unresolved=false
   for _,line in ipairs(item.text) do
    if type(line)~='string' then return nil end
    local clean=line:gsub('{[^}]*}','')
    clean=clean:gsub('#(%d+)#',function(index)
     local value=vars and vars[tonumber(index)]
     if value==nil then unresolved=true;return '?' end
     return tostring(value)
    end)
    lines[#lines+1]=clean
   end
   return #lines>0 and table.concat(lines,' ') or nil,unresolved
  end,public)
  core.release_created(before)
  return snapshot
 end
 function P:draw()
  if not self:visible() then return end
  local lg=love.graphics;lg.push('all');lg.origin();lg.setShader();lg.setScissor()
  local r,input,send,close=self:regions();local s=r.scale
  local font=self:font(math.floor(20*s));local small=self:font(math.floor(16*s));local title=self:font(math.floor(24*s))
  local function box(rect,c)lg.setColor(c);lg.rectangle('fill',rect.x,rect.y,rect.w,rect.h,5*s,5*s)end
  local function label(text,x,y,width,f,c,align)lg.setFont(f or font);lg.setColor(c or colours.text);lg.printf(text,x,y,width,align or 'left')end
  local function button(rect,text,c)box(rect,c or colours.well);label(text,rect.x+5*s,rect.y+(rect.h-font:getHeight())/2,rect.w-10*s,font,colours.text,'center')end
  local function icon(rect,kind,c)
   box(rect,c or colours.well);lg.setColor(colours.text)
   local cy=rect.y+rect.h/2;local cx=rect.x+rect.w/2
   lg.setLineWidth(4*s)
   if kind=='collapse' then lg.line(cx-13*s,cy,cx+13*s,cy)
   elseif kind=='settings' then
    lg.line(cx-12*s,cy-8*s,cx+12*s,cy-8*s);lg.line(cx-12*s,cy,cx+12*s,cy);lg.line(cx-12*s,cy+8*s,cx+12*s,cy+8*s)
    lg.line(cx-4*s,cy-12*s,cx-4*s,cy-4*s);lg.line(cx+5*s,cy-4*s,cx+5*s,cy+4*s);lg.line(cx-2*s,cy+4*s,cx-2*s,cy+12*s)
   else lg.line(cx,cy+12*s,cx,cy-12*s);lg.line(cx-10*s,cy-2*s,cx,cy-12*s,cx+10*s,cy-2*s) end
  end
  if not self.open then
   local e=self:entry();box({x=e.x-2,y=e.y-2,w=e.w+4,h=e.h+4},colours.gold);box(e,colours.bg)
   label(self:t('title'),e.x+10*s,e.y+9*s,e.w-45*s,font);label('Fn+F8',e.x+e.w-62*s,e.y+13*s,60*s,small,colours.gold)
   lg.pop();return
  end
  box({x=r.x+5*s,y=r.y+7*s,w=r.w,h=r.h},{0,0,0,0.4});box(r,colours.gold)
  box({x=r.x+3*s,y=r.y+3*s,w=r.w-6*s,h=r.h-6*s},colours.bg)
  local settings=self:settings_regions()
  label(self:t('title'),r.x+18*s,r.y+16*s,r.w-165*s,title,colours.gold);icon(close,'collapse')
  if self:bridge_active() then icon(settings.gear,'settings') end
  local status=(self.pending or self.remote_pending) and self:t('thinking') or self.settings_error and self:t('error_'..self.settings_error) or self:bridge_active() and self.bridge_connected==false and self:t('bridge_offline') or self.model_name and self:t('configured',{model=self.model_name}) or self:t(self.config_error=='bad_config' and 'invalid_config' or 'disconnected')
  label(status,r.x+18*s,r.y+52*s,r.w-36*s,small,colours.muted)
  self.snapshot=self:read_snapshot();local snap=self.snapshot
  label(self:t('summary',{phase=self:t(snap.phase),ante=snap.ante,money=snap.money,jokers=snap.jokers,slots=snap.slots}),r.x+18*s,r.y+82*s,r.w-36*s,small)
  local items={}
  local held={};for _,item in ipairs(snap.consumables) do held[#held+1]=item.hidden and '?' or item.name end
  local consumable_summary=#held>0 and self:t('consumables')..': '..table.concat(held,', ') or nil
  if snap.pack then
   items[#items+1]=self:t('pack_choices',{count=snap.pack.choices_left})
   for _,item in ipairs(snap.pack.options) do items[#items+1]=item.hidden and '?' or item.name end
   if consumable_summary then items[#items+1]=consumable_summary end
  else
   if consumable_summary then items[#items+1]=consumable_summary end
   for _,item in ipairs(snap.shop)do items[#items+1]=item.name..' $'..item.cost end
  end
  local full_summary=table.concat(items,' · ')
  local short_summary,clipped=core.fit_line(full_summary,r.w-36*s,function(value)return small:getWidth(value)end)
  self.details_truncated=clipped and full_summary~=''
  self.details_text=table.concat(items,'\n')
  lg.setScissor(r.x+18*s,r.y+110*s,r.w-36*s,32*s)
  label(short_summary,r.x+18*s,r.y+110*s,r.w-36*s,small,colours.muted);lg.setScissor()
  local chat={x=r.x+18*s,y=r.y+154*s,w=r.w-36*s,h=input.y-r.y-168*s}
  local content=self:chat_content();local total=0
  local heights={}
  for i,m in ipairs(content) do local _,lines=font:getWrap(m.text,chat.w-24*s);heights[i]=#lines*font:getHeight()+42*s;total=total+heights[i]+12*s end
  self.maxscroll=math.max(0,total-chat.h);self.scroll=math.min(self.scroll,self.maxscroll)
  lg.setScissor(chat.x,chat.y,chat.w,math.max(0,chat.h))
  local y=chat.y-math.max(0,total-chat.h)+self.scroll
  for i,m in ipairs(content)do
   box({x=chat.x,y=y,w=chat.w,h=heights[i]},m.role=='user' and {0.19,0.23,0.22,1} or colours.well)
   label(self:t(m.role=='user' and 'you' or 'assistant'),chat.x+12*s,y+8*s,chat.w-24*s,small,colours.gold)
   label(m.text,chat.x+12*s,y+30*s,chat.w-24*s,font,m.thinking and colours.muted or nil)
   y=y+heights[i]+12*s
  end
  lg.setScissor()
  if self.maxscroll>0 then
   local barh=math.max(18*s,chat.h*chat.h/total)
   box({x=chat.x+chat.w-3*s,y=chat.y+(chat.h-barh)*(1-self.scroll/self.maxscroll),w=3*s,h=barh},colours.gold)
  end
  box(input,self.focused and {0.22,0.28,0.28,1} or colours.well);icon(send,'send',colours.red)
  local tx=input.x+10*s;local textw=input.w-send.w-28*s
  lg.setScissor(tx,input.y+8*s,textw,input.h-16*s)
  lg.setFont(font)
  local prefix=self.editor.text:sub(1,self.editor.cursor)
  local caret=font:getWidth(prefix..self.composition)
  local offset=math.max(0,caret-textw+8*s)
  if self.editor.selected then box({x=tx-offset,y=input.y+18*s,w=font:getWidth(self.editor.text),h=font:getHeight()}, {0.35,0.40,0.31,1})end
  lg.setColor(colours.text)
  local display=self.editor.text:sub(1,self.editor.cursor)..self.composition..self.editor.text:sub(self.editor.cursor+1)
  if display=='' then lg.setColor(colours.muted);display=self:t('placeholder')end
  if self.suggested and not self.focused and self.editor.text~='' then
   lg.push();lg.translate(tx-offset,input.y+18*s);lg.shear(-0.14,0);lg.print(display,0,0);lg.pop()
  else lg.print(display,tx-offset,input.y+18*s) end
  if self.focused and math.floor(now()*2)%2==0 then
   lg.setColor(colours.gold);lg.rectangle('fill',tx+caret-offset,input.y+16*s,2*s,font:getHeight()+4*s)
  end
  if self.composition~='' then
   lg.setColor(colours.gold);lg.line(tx+font:getWidth(prefix)-offset,input.y+42*s,tx+caret-offset,input.y+42*s)
  end
  lg.setScissor()
  lg.setColor(colours.gold);lg.rectangle('fill',r.x+3*s,r.y+r.h/2-20*s,3*s,40*s)
  if self.details_open and self.details_truncated and not self.settings_open then
   local _,popup=self:details_regions()
   box(popup,colours.gold)
   box({x=popup.x+2*s,y=popup.y+2*s,w=popup.w-4*s,h=popup.h-4*s},colours.bg)
   local _,lines=small:getWrap(self.details_text,popup.w-20*s)
   self.details_maxscroll=math.max(0,#lines*small:getHeight()+16*s-popup.h)
   self.details_scroll=math.min(self.details_scroll,self.details_maxscroll)
   lg.setScissor(popup.x+8*s,popup.y+6*s,popup.w-16*s,popup.h-12*s)
   label(self.details_text,popup.x+10*s,popup.y+8*s-self.details_scroll,popup.w-20*s,small)
   lg.setScissor()
  end
  if self.settings_open and self:bridge_active() then
   local w,h=lg.getDimensions()
   lg.setColor(0,0,0,0.53);lg.rectangle('fill',0,0,w,h)
   local ui=settings;box(ui.card,colours.gold)
   box({x=ui.card.x+2*s,y=ui.card.y+2*s,w=ui.card.w-4*s,h=ui.card.h-4*s},colours.bg)
   local function option(rect,caption,active,disabled)
    box(rect,active and {0.43,0.32,0.15,1} or disabled and {0.12,0.16,0.16,1} or colours.well)
    label(caption,rect.x+3*s,rect.y+(rect.h-small:getHeight())/2,rect.w-6*s,small,active and colours.gold or disabled and colours.muted or colours.text,'center')
   end
   label(self:t('setting_model'),ui.card.x+12*s,ui.card.y+13*s,ui.card.w-24*s,small,colours.gold)
   for _,item in ipairs(ui.models)do option(item,item.name,self.remote_settings and self.remote_settings.model==item.id) end
   label(self:t('setting_effort'),ui.card.x+12*s,ui.card.y+89*s,ui.card.w-24*s,small,colours.gold)
   for _,item in ipairs(ui.efforts)do option(item,self:t('effort_'..item.id),self.remote_settings and self.remote_settings.effort==item.id)end
   label(self:t('setting_goal'),ui.card.x+12*s,ui.card.y+163*s,ui.card.w-24*s,small,colours.gold)
   for _,item in ipairs(ui.goals)do option(item,self:t('goal_'..item.id)..(item.enabled and '' or self:t('goal_unavailable')),
    (self.remote_settings and self.remote_settings.play_goal or 'clear')==item.id,not item.enabled)end
   label(self:t('setting_location'),ui.card.x+12*s,ui.card.y+233*s,ui.card.w-24*s,small,colours.gold)
   option(ui.inside,self:t('location_inside'),self.mode~='outside')
   option(ui.outside,self:t('location_outside'),self.mode=='outside')
  end
  lg.pop()
 end
 return P
end
