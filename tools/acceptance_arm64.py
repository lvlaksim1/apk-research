"""Real Android 15 Google APIs x86_64 native-bridge acceptance.

Creates an arm64-v8a-only Android application; installs it using the exact
apk-research XAPK installer; then verifies an ARM64 JNI_OnLoad call in logcat.
Requires an already-running Google APIs AVD and Android SDK/NDK/JDK.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from apk_research.desktop.android_runtime import AndroidRuntime
from apk_research.desktop.components import ComponentManager

PACKAGE = "org.apkresearch.armacceptance"
LOG_TAG = "APK-RESEARCH-ARM"
MARKER = "ARM64_NATIVE_LOADED"
STOREPASS = "changeit"


def run(command: list[str], timeout: float = 120) -> str:
    result = subprocess.run(
        [str(x) for x in command],
        text=True, capture_output=True, errors="replace", timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}"
            + "\n" + result.stdout + "\n" + result.stderr
        )
    return result.stdout


def link_tool(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source)
    except OSError:
        shutil.copy2(source, target)
        target.chmod(0o755)


def find_clang(sdk: Path) -> Path:
    candidates = sorted(
        (sdk / "ndk").glob("*/toolchains/llvm/prebuilt/linux-x86_64/bin/"
                           "aarch64-linux-android24-clang")
    )
    if not candidates:
        raise RuntimeError("Android NDK aarch64 compiler was not found")
    return candidates[-1]


def main() -> int:
    sdk = Path(
        os.environ.get("ANDROID_HOME")
        or os.environ["ANDROID_SDK_ROOT"]
    ).resolve()
    tools = sdk / "build-tools" / "35.0.0"
    aapt2, apksigner, d8 = (
        tools / "aapt2", tools / "apksigner", tools / "d8"
    )
    android_jar = sdk / "platforms" / "android-35" / "android.jar"
    adb = sdk / "platform-tools" / "adb"
    clang = find_clang(sdk)
    keytool = shutil.which("keytool")
    javac = shutil.which("javac")
    if not keytool or not javac:
        raise RuntimeError("JDK keytool/javac not found")
    for p in (aapt2, apksigner, d8, android_jar, adb, clang):
        if not p.is_file():
            raise RuntimeError(f"Missing Android SDK tool: {p}")

    abis = run([str(adb), "-s", "emulator-5554", "shell",
                "getprop", "ro.product.cpu.abilist"])
    print("Guest ABI list:", abis.strip(), flush=True)
    if "arm64-v8a" not in [abi.strip() for abi in abis.split(",")]:
        raise RuntimeError("Google APIs guest does not advertise arm64-v8a")
    uid = run([str(adb), "-s", "emulator-5554", "shell", "id", "-u"])
    if uid.strip() != "0":
        raise RuntimeError("Google APIs image does not support adb root")

    with tempfile.TemporaryDirectory(prefix="apk-research-arm64-proof-") as tmp:
        work = Path(tmp)
        manifest = work / "AndroidManifest.xml"
        manifest.write_text(
            f"""<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{PACKAGE}" android:versionCode="1" android:versionName="1">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35" />
    <application android:label="ARM64 Proof" android:extractNativeLibs="true">
      <activity android:name=".MainActivity" android:exported="true">
        <intent-filter>
          <action android:name="android.intent.action.MAIN" />
          <category android:name="android.intent.category.LAUNCHER" />
        </intent-filter>
      </activity>
    </application>
</manifest>
""", encoding="utf-8",
        )
        source = work / "MainActivity.java"
        source.write_text(
            f"""package {PACKAGE};
import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
public final class MainActivity extends Activity {{
    @Override public void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        try {{
            System.loadLibrary("armproof");
            Log.i("{LOG_TAG}", "{MARKER}");
        }} catch (Throwable error) {{
            Log.e("{LOG_TAG}", "NATIVE_LOAD_FAILED: " + error);
            throw new RuntimeException(error);
        }}
    }}
}}
""", encoding="utf-8",
        )
        javadir = work / "jclasses"
        javadir.mkdir()
        run([str(javac), "-source", "8", "-target", "8",
             "-cp", str(android_jar), "-d", str(javadir), str(source)])
        dexdir = work / "dex"
        dexdir.mkdir()
        run([str(d8), "--min-api", "23", "--lib", str(android_jar),
             "--output", str(dexdir), str(javadir / "org/apkresearch/"
                                               "armacceptance/MainActivity.class")])
        native_src = work / "native.c"
        native_src.write_text(
            '__attribute__((visibility("default"))) '
            'int JNI_OnLoad(void *vm, void *unused) {'
            'return 0x00010006; }\n',
            encoding="utf-8",
        )
        so = work / "libarmproof.so"
        run([str(clang), "-shared", "-fPIC", "-o", str(so), str(native_src)])
        unsigned = work / "unsigned.apk"
        apk = work / "base.apk"
        run([str(aapt2), "link", "-o", str(unsigned), "--manifest",
             str(manifest), "-I", str(android_jar)])
        with zipfile.ZipFile(unsigned, "a") as a:
            a.write(dexdir / "classes.dex", "classes.dex")
            a.write(so, "lib/arm64-v8a/libarmproof.so")
        keystore = work / "proof.jks"
        run([str(keytool), "-genkeypair", "-noprompt", "-keystore",
             str(keystore), "-storepass", STOREPASS,
             "-keypass", STOREPASS, "-alias", "armproof", "-keyalg",
             "RSA", "-keysize", "2048", "-validity", "1",
             "-dname", "CN=apk-research"])
        run([str(apksigner), "sign", "--ks", str(keystore),
             "--ks-pass", "pass:" + STOREPASS,
             "--key-pass", "pass:" + STOREPASS,
             "--out", str(apk), str(unsigned)])
        xapk = work / "arm64-only.xapk"
        with zipfile.ZipFile(xapk, "w") as archive:
            archive.write(apk, "base.apk")
        components = ComponentManager(work / "components")
        components.select_profile("google_apis")
        link_tool(components.paths.adb, adb)
        link_tool(components.paths.aapt2, aapt2)
        runtime = AndroidRuntime(components)
        try:
            installed = runtime.install_package(xapk)
            if installed != PACKAGE:
                raise RuntimeError(f"Installed package mismatch: {installed}")
            run([str(adb), "-s", "emulator-5554", "logcat", "-c"])
            run([str(adb), "-s", "emulator-5554", "shell", "am", "start",
                 "-n", f"{PACKAGE}/.MainActivity"])
            deadline = time.monotonic() + 45
            last_log = ""
            while time.monotonic() < deadline:
                last_log = run([str(adb), "-s", "emulator-5554",
                                "logcat", "-d", "-s", f"{LOG_TAG}:I", "*:S"])
                if MARKER in last_log:
                    print("ARM64_NATIVE_LOADED: PASS", flush=True)
                    return 0
                if "NATIVE_LOAD_FAILED" in last_log:
                    break
                time.sleep(2)
            raise RuntimeError("ARM64 native library did not load. " + last_log[-4000:])
        finally:
            subprocess.run([str(adb), "-s", "emulator-5554",
                            "uninstall", PACKAGE], check=False,
                           capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
