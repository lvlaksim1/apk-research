# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).parent
source_root = project_root / "src"
entry_script = source_root / "mobile_research" / "desktop_entry.py"

a = Analysis(
    [str(entry_script)],
    pathex=[str(source_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "grpc",
        "grpc._cython.cygrpc",
        "google.protobuf",
        "google.protobuf.descriptor_pb2",
        "google.protobuf.message_factory",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MobileResearch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MobileResearch",
)
