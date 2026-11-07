"""只安装本项目的运行文件；已有安装先移到 Mods 目录之外备份。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import tempfile

parser = argparse.ArgumentParser(description='Install Cardwisp into Balatro Mods without touching other mods or saves. 安装小丑牌灵；不修改其他插件或存档。')
parser.add_argument('--mods-dir', type=Path, required=True, help='Balatro Mods folder / Balatro 的 Mods 目录')
args = parser.parse_args()
source = Path(__file__).resolve().parents[1]
mods = args.mods_dir.expanduser().resolve()
target = mods / 'balatro-assistant'
if target.is_symlink():
    sys.exit('The target is a symlink; check the install location first. 目标是符号链接，请先人工确认安装位置。')
if target.exists():
    try:
        manifest = json.loads((target / 'balatro-assistant.json').read_text())
        own = manifest.get('id') == 'balatro_assistant'
    except (OSError, ValueError, AttributeError):
        own = False
    if not own:
        sys.exit('The target folder exists but does not look like Cardwisp; nothing changed. 目标目录存在但无法确认属于本插件，未修改。')
mods.mkdir(parents=True, exist_ok=True)
# 先构造完整安装，不在 Mods 下暂存半成品或重复插件。
with tempfile.TemporaryDirectory(prefix='.assistant-install-', dir=mods.parent) as temp:
    stage = Path(temp) / 'balatro-assistant'
    stage.mkdir()
    for name in ('main.lua', 'balatro-assistant.json', 'modules', 'locales', 'LICENSE'):
        src, dst = source / name, stage / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    backup = None
    if target.exists():
        backup = mods.parent / 'assistant-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.rename(backup)
    try:
        stage.rename(target)
    except OSError:
        if backup is not None:
            backup.rename(target)
        raise
    if backup is not None:
        print('Backed up / 已备份：', backup)
print('Installed / 已安装：', target)
print('Restart the game with Lovely / Steamodded to load it. 重新启动启用了 Lovely / Steamodded 的游戏后生效。')
