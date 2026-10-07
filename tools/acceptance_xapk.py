from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from apk_research.desktop.android_runtime import AndroidRuntime
from apk_research.desktop.components import ComponentManager


SERIAL = "emulator-5554"
PACKAGE = "org.apkresearch.xapkacceptance"
STOREPASS = "changeit"


def _sdk_root() -> Path:
    value = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not value:
        raise RuntimeError("ANDROID_HOME/ANDROID_SDK_ROOT is not set")
    return Path(value).resolve()


def _newest_build_tools(root: Path) -> Path:
    base = root / "build-tools"
    versions = sorted(
        (path for path in base.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    if not versions:
        raise RuntimeError("Android build-tools are missing")
    return versions[-1]


def _run(command: list[str], *, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + "\n"
            + result.stdout
            + "\n"
            + result.stderr
        )
    return result


def _link_tool(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source)
    except OSError:
        shutil.copy2(source, target)
        target.chmod(0o755)


def main() -> int:
    sdk = _sdk_root()
    build_tools = _newest_build_tools(sdk)
    aapt2 = build_tools / "aapt2"
    apksigner = build_tools / "apksigner"
    adb = sdk / "platform-tools" / "adb"
    android_jar = sdk / "platforms" / "android-35" / "android.jar"
    keytool = shutil.which("keytool")

    for path in (aapt2, apksigner, adb, android_jar):
        if not path.is_file():
            raise RuntimeError(f"Required Android tool is missing: {path}")
    if not keytool:
        raise RuntimeError("keytool is missing")

    with tempfile.TemporaryDirectory(prefix="apk-research-xapk-acceptance-") as raw:
        root = Path(raw)
        manifest = root / "AndroidManifest.xml"
        manifest.write_text(
            """<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.apkresearch.xapkacceptance"
    android:versionCode="1"
    android:versionName="1.0">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35" />
    <application android:hasCode="false" android:label="XAPK Acceptance">
        <activity
            android:name="android.app.Activity"
            android:exported="true"
            android:label="XAPK Acceptance">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""",
            encoding="utf-8",
        )

        unsigned = root / "base-unsigned.apk"
        base_apk = root / "base.apk"
        keystore = root / "acceptance.jks"

        _run(
            [
                str(aapt2),
                "link",
                "-o",
                str(unsigned),
                "--manifest",
                str(manifest),
                "-I",
                str(android_jar),
            ]
        )
        _run(
            [
                str(keytool),
                "-genkeypair",
                "-noprompt",
                "-keystore",
                str(keystore),
                "-storepass",
                STOREPASS,
                "-keypass",
                STOREPASS,
                "-alias",
                "xapk",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "1",
                "-dname",
                "CN=apk-research",
            ]
        )
        _run(
            [
                str(apksigner),
                "sign",
                "--ks",
                str(keystore),
                "--ks-pass",
                f"pass:{STOREPASS}",
                "--key-pass",
                f"pass:{STOREPASS}",
                "--out",
                str(base_apk),
                str(unsigned),
            ]
        )

        xapk = root / "acceptance.xapk"
        obb_name = f"main.1.{PACKAGE}.obb"
        obb_bytes = b"apk-research xapk acceptance obb\n"
        with zipfile.ZipFile(
            xapk,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.write(base_apk, "base.apk")
            archive.writestr(
                f"Android/obb/{PACKAGE}/{obb_name}",
                obb_bytes,
            )
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "package_name": PACKAGE,
                        "version_code": 1,
                    }
                ),
            )

        manager = ComponentManager(root / "managed")
        _link_tool(manager.paths.adb, adb)
        _link_tool(manager.paths.aapt2, aapt2)

        runtime = AndroidRuntime(manager)
        events: list[str] = []

        def progress(message: str, current, total) -> None:
            events.append(message)
            print(
                json.dumps(
                    {
                        "event": "xapk_progress",
                        "message": message,
                        "current": current,
                        "total": total,
                    },
                    ensure_ascii=False,
                )
            )

        try:
            installed = runtime.install_package(xapk, progress)
            if installed != PACKAGE:
                raise RuntimeError(
                    f"Unexpected installed package: {installed}"
                )

            pm = _run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "shell",
                    "pm",
                    "path",
                    PACKAGE,
                ]
            )
            if "package:" not in pm.stdout:
                raise RuntimeError(
                    "Synthetic XAPK package is not installed"
                )

            remote_obb = f"/sdcard/Android/obb/{PACKAGE}/{obb_name}"
            obb = _run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "shell",
                    "cat",
                    remote_obb,
                ]
            )
            if obb.stdout.encode("utf-8") != obb_bytes:
                raise RuntimeError(
                    "Synthetic XAPK OBB payload does not match"
                )

            favorites = _run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "shell",
                    "content",
                    "query",
                    "--uri",
                    "content://com.android.launcher3.settings/favorites",
                ]
            )
            if (
                f"package={PACKAGE};" not in favorites.stdout
                and f"component={PACKAGE}/" not in favorites.stdout
            ):
                raise RuntimeError(
                    "Synthetic XAPK home shortcut was not created"
                )

            home = _run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "shell",
                    "dumpsys",
                    "activity",
                    "activities",
                ]
            )
            if "com.android.launcher3" not in home.stdout:
                raise RuntimeError(
                    "Launcher3 is not visible after XAPK installation"
                )

            if not any("Установка XAPK" in item for item in events):
                raise RuntimeError(
                    "Runtime did not report XAPK installation path"
                )

            print(
                json.dumps(
                    {
                        "event": "xapk_acceptance",
                        "status": "ok",
                        "package": PACKAGE,
                        "obb": remote_obb,
                        "home_shortcut": True,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        finally:
            subprocess.run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "uninstall",
                    PACKAGE,
                ],
                capture_output=True,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
