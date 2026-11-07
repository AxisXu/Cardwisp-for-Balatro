"""使用真实 Lua 5.1 / LuaJIT 运行行为测试，不依赖游戏资源内容。"""
import ctypes
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
os.chdir(root)
path = os.environ.get('BALATRO_LUA_LIBRARY') or str(Path.home() / 'Library/Application Support/Steam/steamapps/common/Balatro/Balatro.app/Contents/Frameworks/Lua.framework/Versions/A/Lua')
lua = ctypes.CDLL(path)
pointer = ctypes.c_void_p
lua.luaL_newstate.restype = pointer
lua.luaL_openlibs.argtypes = [pointer]
lua.luaL_loadfile.argtypes = [pointer, ctypes.c_char_p]
lua.lua_pcall.argtypes = [pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int]
lua.lua_tolstring.argtypes = [pointer, ctypes.c_int, pointer]
lua.lua_tolstring.restype = ctypes.c_char_p
lua.lua_close.argtypes = [pointer]
state = lua.luaL_newstate()
lua.luaL_openlibs(state)
status = lua.luaL_loadfile(state, (sys.argv[1] if len(sys.argv) > 1 else 'tests/core_test.lua').encode())
if not status:
    status = lua.lua_pcall(state, 0, -1, 0)
if status:
    print(lua.lua_tolstring(state, -1, None).decode(), file=sys.stderr)
lua.lua_close(state)
sys.exit(bool(status))
