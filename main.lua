local mod=SMODS.current_mod
local function load(path)return assert(SMODS.load_file(path))() end
local core=load('modules/core.lua')
local tr=core.translator({['en-us']=load('locales/en-us.lua'),zh_CN=load('locales/zh_CN.lua')})
local model=load('modules/model.lua')({
 read_config=function()return love.filesystem.read('cardwisp-model.json')end,
 encode=function(value)return (JSON or require('json')).encode(value)end,
 decode=function(value)return (JSON or require('json')).decode(value)end,
 request=function(url,options,callback)return require('SMODS.https').asyncRequest(url,options,callback)end,
})
local panel=load('modules/panel.lua')(core,tr,model)
mod.assistant=panel
panel:update()
local function after(name,fn)
 local original=love[name]
 love[name]=function(...)if original then original(...)end;fn(...)end
end
local function input(name,fn)
 local original=love[name]
 love[name]=function(...)if fn(...)then return end;if original then return original(...)end end
end
-- 起始事件归助手的按键/鼠标，结束事件也归助手，避免关闭或拖出后穿透。
local keys,buttons={},{}
input('keypressed',function(key,...)
 if keys[key]=='panel' then if panel.focused then panel:keypressed(key,...)end;return true end
 if keys[key]=='game' then return panel.focused end
 if panel:keypressed(key,...)then keys[key]='panel';return true end
 keys[key]='game'
end)
input('keyreleased',function(key)local owner=keys[key];keys[key]=nil;return owner=='panel' end)
input('mousepressed',function(x,y,button,...)
 if panel:mousepressed(x,y,button,...)then buttons[button]=true;return true end
end)
input('mousereleased',function(x,y,button)
 if buttons[button]then buttons[button]=nil;panel:mousereleased(x,y,button);return true end
end)
input('mousemoved',function(...)return panel:mousemoved(...)end)
input('wheelmoved',function(...)return panel:wheelmoved(...)end)
input('textinput',function(...)return panel:textinput(...)end)
input('textedited',function(...)return panel:textedited(...)end)
local update=love.update
love.update=function(...)panel:update();if update then update(...)end end
after('draw',function()panel:draw()end)
local focus=love.focus
love.focus=function(focused,...)if not focused then panel:focus(false);panel.resizing=nil end;if focus then focus(focused,...)end end
