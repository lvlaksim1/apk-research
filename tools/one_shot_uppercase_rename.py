from pathlib import Path
import subprocess

root = Path('.')
script_file = Path('tools/one_shot_uppercase_rename.py')
skip_dirs = {'.git', '.venv', 'venv', '__pycache__', 'dist', 'build', 'installer'}

def is_workflow(path: Path) -> bool:
    parts = path.parts
    return len(parts) >= 2 and parts[0] == '.github' and parts[1] == 'workflows'

changed = 0
for path in root.rglob('*'):
    if not path.is_file() or is_workflow(path):
        continue
    if any(part in skip_dirs for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        continue
    updated = text.replace('MOBILE_RESEARCH', 'APK_RESEARCH')
    if updated != text:
        path.write_text(updated, encoding='utf-8', newline='\n')
        changed += 1

if script_file.exists():
    script_file.unlink()

for path in root.rglob('*'):
    if not path.is_file() or is_workflow(path):
        continue
    if any(part in skip_dirs for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        continue
    if 'MOBILE_RESEARCH' in text:
        raise SystemExit(f'Uppercase old namespace remains in {path}')

subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
subprocess.run(['git', 'add', '-A'], check=True)
subprocess.run(['git', 'commit', '-m', 'Rename environment namespace to APK_RESEARCH'], check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD:main'], check=True)
print(f'Updated {changed} files')
