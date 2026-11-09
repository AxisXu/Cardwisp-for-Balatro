"""运行本里程碑全部自动验证；任一失败即返回失败。"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for suite in ('core_test.lua', 'model_test.lua', 'model_panel_test.lua', 'settings_panel_test.lua', 'direct_mode_panel_test.lua', 'scene_sync_test.lua', 'panel_test.lua', 'input_ownership_test.lua', 'draw_test.lua'):
    subprocess.run([sys.executable, str(root / 'tests/run.py'), 'tests/' + suite], check=True)
subprocess.run([sys.executable, str(root / 'tests/install_test.py')], check=True)
subprocess.run([sys.executable, str(root / 'tests/cli_bridge_test.py')], check=True)
subprocess.run([sys.executable, '-m', 'unittest', 'tests.answer_format_test'], cwd=str(root), check=True)
subprocess.run([sys.executable, str(root / 'tests/shop_decision_test.py')], check=True)
subprocess.run([sys.executable, str(root / 'tests/scene_decision_test.py')], check=True)
print('全部自动验证通过；真实游戏交互另行验收。')
