from pathlib import Path
import re
import subprocess

root = Path('.')
workflow = root / '.github/workflows/rename-to-apk-research.yml'
script_file = root / 'tools/one_shot_rename_to_apk_research.py'

replacements = [
    ('MobileResearchSetup', 'apk-research-setup'),
    ('Mobile Research', 'apk-research'),
    ('MobileResearch', 'apk-research'),
    ('mobile-research', 'apk-research'),
    ('mobile_research', 'apk_research'),
]

skip_dirs = {'.git', '.venv', 'venv', '__pycache__', 'dist', 'build', 'installer'}
for path in list(root.rglob('*')):
    if not path.is_file():
        continue
    if any(part in skip_dirs for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        continue
    updated = text
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding='utf-8', newline='\n')

rename_pairs = [
    (Path('src/mobile_research'), Path('src/apk_research')),
    (Path('packaging/MobileResearch.spec'), Path('packaging/apk-research.spec')),
    (Path('packaging/mobile-research.iss'), Path('packaging/apk-research.iss')),
]
for old, new in rename_pairs:
    if old.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)

pyproject = Path('pyproject.toml')
text = pyproject.read_text(encoding='utf-8')
text = re.sub(r'(?m)^version = "0\.14\.0"$', 'version = "0.15.0"', text, count=1)
pyproject.write_text(text, encoding='utf-8', newline='\n')

init_file = Path('src/apk_research/__init__.py')
text = init_file.read_text(encoding='utf-8')
text = text.replace('__version__ = "0.14.0"', '__version__ = "0.15.0"')
lines = [line for line in text.splitlines() if not line.startswith('# v0.14.0 ')]
insert_at = next((i + 1 for i, line in enumerate(lines) if line.startswith('__version__ = ')), len(lines))
lines.insert(insert_at, '# v0.15.0 completes the product rename to apk-research.')
init_file.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8', newline='\n')

readme = Path('README.md')
text = readme.read_text(encoding='utf-8')
marker = '# apk-research\n\n'
if not text.startswith(marker):
    raise SystemExit('README title was not renamed')
section = '''## v0.15.0 — Product rename to apk-research

Начиная с v0.15.0 программа, репозиторий, Python distribution/namespace, GUI, CLI, EXE, installer, release assets, каталоги установки и техническая документация используют единое имя `apk-research`.

Это rename-only release: validated hidden Emulator → gRPC/MMAP runtime, v0.10.5 clean-launch sequencing, collectors, Research ZIP schemas, raw PCAP, attribution, Timeline и Network Analyzer semantics не меняются.

'''
readme.write_text(marker + section + text[len(marker):], encoding='utf-8', newline='\n')

changelog = Path('CHANGELOG.md')
text = changelog.read_text(encoding='utf-8')
marker = '# Changelog\n\nAll notable apk-research changes are recorded here.\n\n'
if not text.startswith(marker):
    raise SystemExit('CHANGELOG header was not renamed')
section = '''## [0.15.0] - 2026-09-17

### Product rename

- Renames the product to `apk-research` across the repository and all user-visible surfaces.
- Renames the Python distribution to `apk-research` and the import namespace to `apk_research`.
- Renames GUI application/QSettings identity, CLI entry points, PyInstaller target, EXE, installation directory and Start-menu/desktop shortcuts.
- Renames packaging sources to `apk-research.spec` and `apk-research.iss`.
- Renames release installer assets to `apk-research-setup_v<version>.exe`.
- Updates workflows, tests, tools and documentation to the new namespace and artifact names.
- Keeps runtime, capture, Research ZIP and evidence semantics unchanged.

'''
changelog.write_text(marker + section + text[len(marker):], encoding='utf-8', newline='\n')

refactoring = Path('REFACTORING.md')
text = refactoring.read_text(encoding='utf-8')
marker = '# Refactoring and Architecture Log\n\n'
section = '''## v0.15.0 — Product identity: apk-research

### Scope

Полная миграция имени продукта. Старое имя удаляется из tracked text files и путей репозитория; canonical product identity становится `apk-research`, Python namespace — `apk_research`.

### Compatibility boundary

AppId Inno Setup сохраняется, чтобы v0.15.0 оставался обновлением существующей Windows-установки, а не независимым продуктом. Forensic/runtime architecture не меняется.

'''
if not text.startswith(marker):
    raise SystemExit('REFACTORING header missing')
refactoring.write_text(marker + section + text[len(marker):], encoding='utf-8', newline='\n')

Path('RELEASE_NOTES.md').write_text('''# apk-research v0.15.0

v0.15.0 completes the product rename to **apk-research**.

## Renamed surfaces

- repository: `apk-research`;
- Python distribution: `apk-research`;
- Python namespace: `apk_research`;
- GUI/QSettings identity: `apk-research`;
- CLI: `apk-research` and `apk-research-gui`;
- standalone executable: `apk-research.exe`;
- PyInstaller target/spec: `apk-research` / `packaging/apk-research.spec`;
- Inno Setup source: `packaging/apk-research.iss`;
- installer/release asset: `apk-research-setup_v0.15.0.exe`;
- installation directory and shortcuts: `apk-research`.

## Compatibility

The Inno Setup AppId is preserved so the renamed application upgrades the existing installation. Capture/runtime behavior and forensic evidence formats are unchanged.
''', encoding='utf-8', newline='\n')

Path('docs/V0.15_APK_RESEARCH_RENAME.md').write_text('''# apk-research v0.15 — complete product rename

v0.15.0 establishes `apk-research` as the single canonical name across source code, packaging, workflows, executable/install artifacts and documentation.

The Python namespace is `apk_research`. The Windows executable is `apk-research.exe`; the release installer is `apk-research-setup_v0.15.0.exe`.

The existing Inno Setup AppId is intentionally preserved for upgrade continuity. No collector, emulator, gRPC/MMAP, clean-launch, PCAP, attribution, Timeline or Research ZIP semantics are changed by this release.
''', encoding='utf-8', newline='\n')

for transient in (workflow, script_file):
    if transient.exists():
        transient.unlink()

forbidden = ('Mobile Research', 'MobileResearch', 'mobile-research', 'mobile_research')
offenders = []
for path in root.rglob('*'):
    if not path.is_file() or any(part in skip_dirs | {'.git'} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        continue
    hits = [token for token in forbidden if token in text or token in str(path)]
    if hits:
        offenders.append((str(path), hits))
if offenders:
    raise SystemExit('Old product name remains: ' + repr(offenders[:100]))

subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
subprocess.run(['git', 'add', '-A'], check=True)
subprocess.run(['git', 'commit', '-m', 'Release apk-research v0.15.0 product rename'], check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD:main'], check=True)
