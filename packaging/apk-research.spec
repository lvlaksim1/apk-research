# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).parent
source_root = project_root / "src"
entry_script = source_root / "apk_research" / "desktop_entry.py"
agent_jar = (
    project_root
    / "build"
    / "android-sidecar"
    / "apk-research-agent.jar"
)
app_icon_ico = (
    project_root
    / "build"
    / "app-icon"
    / "apk-research.ico"
)
route_executable = (
    project_root / "build" / "android-route" / "apk-research-https-route"
)
app_icon_png = (
    project_root
    / "build"
    / "app-icon"
    / "apk-research-icon.png"
)
if not agent_jar.is_file():
    raise RuntimeError(
        "Android sidecar agent was not built: "
        + str(agent_jar)
    )
if not route_executable.is_file():
    raise RuntimeError("Android HTTPS route executable was not built")
if not app_icon_ico.is_file() or not app_icon_png.is_file():
    raise RuntimeError(
        "Application icon was not built: "
        + str(app_icon_ico)
    )

a = Analysis(
    [str(entry_script)],
    pathex=[str(source_root)],
    binaries=[],
    datas=[
        (
            str(route_executable),
            "apk_research/resources",
        ),
        (
            str(agent_jar),
            "apk_research/resources",
        ),
        (
            str(app_icon_png),
            "apk_research/resources",
        ),
    ],
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
    name="apk-research",
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
    icon=str(app_icon_ico),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="apk-research",
)
