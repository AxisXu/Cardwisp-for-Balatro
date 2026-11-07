-- 仿照游戏 Controller 行为：长按键状态，以及 locked 时拒绝鼠标释放。
local mx,my=0,0
local held={}
G={STAGE=1,STAGES={RUN=1},STATE=4,STATES={SHOP=4},GAME={},SETTINGS={},CONTROLLER={locks={}}}
love={graphics={getDimensions=function()return 1280,720 end},timer={getTime=function()return 10 end},
 keyboard={setTextInput=function()end,setKeyRepeat=function()end,hasKeyRepeat=function()return false end,isDown=function()return true end},
 mouse={getPosition=function()return mx,my end},
 keypressed=function(k)held[k]=true end,keyreleased=function(k)held[k]=nil end,
 mousepressed=function()G.CONTROLLER.is_cursor_down=true end,
 mousereleased=function()if G.CONTROLLER.locked then return end;G.CONTROLLER.is_cursor_down=false end,
 update=function()G.CONTROLLER.locked=false;for _,v in pairs(G.CONTROLLER.locks)do if v then G.CONTROLLER.locked=true end end end}
SMODS={current_mod={},load_file=function(p)return loadfile(p)end}
dofile('main.lua');local p=SMODS.current_mod.assistant
love.keypressed('f8');love.keyreleased('f8')
local r,input=p:regions()
love.keypressed('r');assert(held.r)
love.mousepressed(input.x+20,input.y+20,1);love.mousereleased(input.x+20,input.y+20,1)
love.keypressed('r','r',true);love.keyreleased('r')
assert(not held.r,'游戏起始的 R 必须收到释放，不能粘住导致重开')
p:focus(false);mx,my=0,0;love.update()
love.mousepressed(0,0,1);assert(G.CONTROLLER.is_cursor_down)
mx,my=r.x+30,r.y+100;love.update();love.mousereleased(mx,my,1)
assert(not G.CONTROLLER.is_cursor_down,'游戏起始的拖拽必须能在面板区域结束')
print('输入归属回归测试通过：游戏先按键、跨面板释放鼠标')
