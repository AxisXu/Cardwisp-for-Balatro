local Model = dofile('modules/model.lua')
local config, sent, finish, payload
local model = Model({
 read_config=function() return config end,
 encode=function(value) if value.phase then return 'snapshot:j_b' end;payload=value;return 'encoded' end,
 decode=function(value)
  if value=='config' then return {url='https://api.example.com/v1/chat/completions',model='test-model',api_key='secret'} end
  if value=='local' then return {url='http://127.0.0.1:1234/v1/chat/completions',model='local'} end
  if value=='bad-http' then return {url='http://example.com/v1/chat/completions',model='test'} end
  if value=='answer' then return {choices={{message={content='先买小丑 A'}}}} end
  if value=='cli_failed' then return {error={code='cli_failed'}} end
  return nil
 end,
 request=function(url,options,callback) sent={url=url,options=options};finish=callback end,
})
local function eq(a,b) assert(a==b,tostring(a)..' ~= '..tostring(b)) end
local function ask(question,snapshot,history)
 local response
 local started,err=model:ask(question,snapshot,'zh_CN',history or {},function(ok,value)response={ok,value}end,'run-1')
 return started,err,function()return response end
end
config=nil
local started,err=ask('买吗？',{phase='shop'})
eq(started,true);eq(sent.url,'http://127.0.0.1:8765/v1/session/message')
eq(payload.question,'买吗？');eq(payload.run_id,'run-1');eq(sent.options.headers.Authorization,nil)
local defaults=model:configuration();eq(defaults.timeout_seconds,315)
eq(model:is_bridge(),true)
local published=model:publish('run-1',{phase='shop'},'zh_CN',function()end)
eq(published,true);eq(sent.url,'http://127.0.0.1:8765/v1/session/snapshot')
eq(payload.language,'zh_CN')
local polled=model:poll(function()end)
eq(polled,true);eq(sent.url,'http://127.0.0.1:8765/v1/session');eq(sent.options.method,'GET')
local changed=model:set_settings({model='gpt-6-luna',effort='medium'},function()end)
eq(changed,true);eq(sent.url,'http://127.0.0.1:8765/v1/session/settings')
local opened=model:open_companion(function()end)
eq(opened,true);eq(sent.url,'http://127.0.0.1:8765/v1/companion/open')
eq(payload.source,'game') -- 请求体不能是空表；游戏 JSON 编码器会把空表编码为 []。
config='bad-http';started,err=ask('买吗？',{})
eq(started,false);eq(err,'bad_config')
config='config'
local snapshot={phase='shop',money=10,owned={{key='j_a',name='小丑 A'}},shop={{key='j_b',name='小丑 B',cost=5}}}
local prior={{role='user',text='上一问'},{role='assistant',text='上一答',source='model'},{role='assistant',text='网络错误',source='error'}}
local reply
started,err,reply=ask('现在买谁？',snapshot,prior)
eq(started,true);eq(sent.url,'https://api.example.com/v1/chat/completions')
eq(sent.options.method,'POST');eq(sent.options.headers.Authorization,'Bearer secret')
eq(sent.options.headers['Content-Type'],'application/json')
eq(payload.model,'test-model');eq(payload.stream,false)
eq(payload.messages[1].role,'system')
assert(payload.messages[2].content:find('j_b',1,true))
eq(payload.messages[3].content,'上一问');eq(payload.messages[4].content,'上一答')
eq(payload.messages[5].content,'现在买谁？')
eq(#payload.messages,5)
finish(200,'answer',{});eq(reply()[1],true);eq(reply()[2],'先买小丑 A')
started,err,reply=ask('再问',snapshot)
finish(401,'',{});eq(reply()[1],false);eq(reply()[2],'auth')
started,err,reply=ask('再问',snapshot)
finish(429,'',{});eq(reply()[2],'rate_limit')
started,err,reply=ask('再问',snapshot)
finish(200,'invalid',{});eq(reply()[2],'bad_response')
config='local';started,err,reply=ask('本地',snapshot)
eq(started,true);eq(sent.options.headers.Authorization,nil)
finish(503,'cli_failed',{});eq(reply()[2],'cli_failed')
print('模型适配器测试通过：配置、请求、上下文、回复和错误')
