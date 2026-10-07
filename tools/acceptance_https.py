from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from apk_research.collectors import HTTPS_TRANSACTIONS_ARTIFACT
from apk_research.https_capture import StagedHttpsCapture
from apk_research.targets import AdbClient


SERIAL = "emulator-5554"
PACKAGE = "org.apkresearch.httpsacceptance"
STOREPASS = "changeit"
TAG = "APKRESEARCH_HTTPS"
URL = "https://example.com/"


def _sdk_root() -> Path:
    value = (
        os.environ.get("ANDROID_HOME")
        or os.environ.get("ANDROID_SDK_ROOT")
    )
    if not value:
        raise RuntimeError(
            "ANDROID_HOME/ANDROID_SDK_ROOT is not set"
        )
    return Path(value).resolve()


def _newest_build_tools(
    root: Path,
) -> Path:
    base = root / "build-tools"
    versions = sorted(
        (
            path
            for path in base.iterdir()
            if path.is_dir()
        ),
        key=lambda path: path.name,
    )
    if not versions:
        raise RuntimeError(
            "Android build-tools are missing"
        )
    return versions[-1]


def _run(
    command: list[str],
    *,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
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
            + "\nstdout:\n"
            + (result.stdout or "")
            + "\nstderr:\n"
            + (result.stderr or "")
        )
    return result


def _build_probe_apk(
    root: Path,
) -> Path:
    sdk = _sdk_root()
    build_tools = _newest_build_tools(
        sdk
    )
    aapt2 = build_tools / "aapt2"
    d8 = build_tools / "d8"
    apksigner = (
        build_tools / "apksigner"
    )
    android_jar = (
        sdk
        / "platforms"
        / "android-35"
        / "android.jar"
    )
    javac = shutil.which("javac")
    keytool = shutil.which("keytool")

    for path in (
        aapt2,
        d8,
        apksigner,
        android_jar,
    ):
        if not path.is_file():
            raise RuntimeError(
                "Required Android tool is missing: "
                + str(path)
            )
    if not javac:
        raise RuntimeError(
            "javac is missing"
        )
    if not keytool:
        raise RuntimeError(
            "keytool is missing"
        )

    manifest = (
        root / "AndroidManifest.xml"
    )
    manifest.write_text(
        """<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.apkresearch.httpsacceptance"
    android:versionCode="1"
    android:versionName="1.0">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35" />
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:label="HTTPS Acceptance"
        android:usesCleartextTraffic="false">
        <activity
            android:name=".MainActivity"
            android:exported="true">
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

    source_dir = (
        root
        / "src"
        / "org"
        / "apkresearch"
        / "httpsacceptance"
    )
    source_dir.mkdir(
        parents=True
    )
    source = (
        source_dir / "MainActivity.java"
    )
    source.write_text(
        f"""package org.apkresearch.httpsacceptance;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public final class MainActivity extends Activity {{
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        new Thread(() -> {{
            try {{
                URL url = new URL("{URL}");
                HttpURLConnection connection =
                    (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(15000);
                connection.setRequestProperty(
                    "User-Agent",
                    "apk-research-https-acceptance/1.0"
                );
                int status = connection.getResponseCode();
                InputStream stream = (
                    status >= 400
                    ? connection.getErrorStream()
                    : connection.getInputStream()
                );
                int total = 0;
                if (stream != null) {{
                    byte[] buffer = new byte[4096];
                    int count;
                    while ((count = stream.read(buffer)) >= 0) {{
                        total += count;
                    }}
                    stream.close();
                }}
                Log.i(
                    "{TAG}",
                    "status=" + status
                    + " bytes=" + total
                    + " url=" + url.toString()
                );
                connection.disconnect();
            }} catch (Throwable error) {{
                Log.e(
                    "{TAG}",
                    "failed=" + error.toString(),
                    error
                );
            }}
        }}, "https-acceptance").start();
    }}
}}
""",
        encoding="utf-8",
    )

    classes = root / "classes"
    classes.mkdir()
    _run(
        [
            str(javac),
            "-source",
            "8",
            "-target",
            "8",
            "-classpath",
            str(android_jar),
            "-d",
            str(classes),
            str(source),
        ]
    )

    dex_dir = root / "dex"
    dex_dir.mkdir()
    class_files = [
        str(path)
        for path in classes.rglob(
            "*.class"
        )
    ]
    if not class_files:
        raise RuntimeError(
            "Probe Java compilation produced no classes"
        )
    _run(
        [
            str(d8),
            "--min-api",
            "23",
            "--output",
            str(dex_dir),
            *class_files,
        ]
    )
    classes_dex = (
        dex_dir / "classes.dex"
    )
    if not classes_dex.is_file():
        raise RuntimeError(
            "d8 did not produce classes.dex"
        )

    unsigned = (
        root / "https-probe-unsigned.apk"
    )
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
    with zipfile.ZipFile(
        unsigned,
        "a",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(
            classes_dex,
            "classes.dex",
        )

    keystore = (
        root / "acceptance.jks"
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
            "https",
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "1",
            "-dname",
            "CN=apk-research HTTPS acceptance",
        ]
    )

    signed = (
        root / "https-probe.apk"
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
            str(signed),
            str(unsigned),
        ]
    )
    return signed


def _wait_for_probe(
    client: AdbClient,
) -> str:
    deadline = time.monotonic() + 35.0
    last = ""
    while time.monotonic() < deadline:
        output = client.shell_output(
            SERIAL,
            "logcat",
            "-d",
            "-s",
            f"{TAG}:V",
            "*:S",
            timeout=10.0,
        )
        last = output
        if "status=200" in output:
            return output
        if "failed=" in output:
            raise RuntimeError(
                "HTTPS probe failed inside Android:\n"
                + output
            )
        time.sleep(1.0)
    raise RuntimeError(
        "HTTPS probe did not complete successfully. "
        "Last logcat output:\n"
        + last
    )


def _read_transactions(
    capture: StagedHttpsCapture,
) -> list[dict]:
    path = (
        capture.root
        / HTTPS_TRANSACTIONS_ARTIFACT
    )
    if not path.is_file():
        return []
    values: list[dict] = []
    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if not line:
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            values.append(value)
    return values


def main() -> int:
    sdk = _sdk_root()
    adb = (
        sdk
        / "platform-tools"
        / "adb"
    )
    if not adb.is_file():
        raise RuntimeError(
            f"ADB is missing: {adb}"
        )
    client = AdbClient(adb)
    details = client.get_target_details(
        SERIAL
    )
    if not details.is_root:
        raise RuntimeError(
            "HTTPS acceptance requires rooted AVD"
        )

    capture: StagedHttpsCapture | None = None
    with tempfile.TemporaryDirectory(
        prefix="apk-research-https-acceptance-"
    ) as raw:
        root = Path(raw)
        apk = _build_probe_apk(
            root
        )
        _run(
            [
                str(adb),
                "-s",
                SERIAL,
                "install",
                "-r",
                "-t",
                str(apk),
            ],
            timeout=120.0,
        )

        try:
            client.shell_output(
                SERIAL,
                "logcat",
                "-c",
            )
            capture = StagedHttpsCapture(
                client,
                SERIAL,
                PACKAGE,
            )
            capture.start()
            launch = client.clean_launch_package(
                SERIAL,
                PACKAGE,
            )
            print(
                json.dumps(
                    {
                        "event": "https_probe_launched",
                        "launch": launch[-1000:],
                    },
                    ensure_ascii=False,
                )
            )

            logcat = _wait_for_probe(
                client
            )
            print(
                json.dumps(
                    {
                        "event": "https_probe_android_success",
                        "logcat": logcat[-2000:],
                    },
                    ensure_ascii=False,
                )
            )

            result = capture.stop()
            transactions = _read_transactions(
                capture
            )
            matching = [
                item
                for item in transactions
                if str(
                    item.get("url")
                    or ""
                ).startswith(URL)
            ]
            if not matching:
                raise RuntimeError(
                    "No decrypted HTTPS transaction "
                    f"for {URL!r}; captured "
                    f"{len(transactions)} total transactions"
                )

            transaction = matching[-1]
            response = (
                transaction.get("response")
                if isinstance(
                    transaction.get("response"),
                    dict,
                )
                else {}
            )
            if int(
                response.get("status_code")
                or 0
            ) != 200:
                raise RuntimeError(
                    "Decrypted HTTPS response status "
                    f"is not 200: {response!r}"
                )
            request_body = (
                transaction.get(
                    "request_body"
                )
                or {}
            )
            response_body = (
                response.get("body")
                or {}
            )
            if int(
                response_body.get("size")
                or 0
            ) <= 0:
                raise RuntimeError(
                    "Decrypted HTTPS response body is empty"
                )
            if str(
                transaction.get("scheme")
                or ""
            ).lower() != "https":
                raise RuntimeError(
                    "Captured transaction is not HTTPS"
                )

            print(
                json.dumps(
                    {
                        "event": "https_interception_acceptance",
                        "status": "ok",
                        "capture": result,
                        "transaction": {
                            "url": transaction.get(
                                "url"
                            ),
                            "method": transaction.get(
                                "method"
                            ),
                            "request_body_bytes": (
                                request_body.get(
                                    "size"
                                )
                            ),
                            "status_code": response.get(
                                "status_code"
                            ),
                            "response_body_bytes": (
                                response_body.get(
                                    "size"
                                )
                            ),
                            "client_http_version": (
                                transaction.get(
                                    "http_version"
                                )
                            ),
                            "server_http_version": (
                                response.get(
                                    "http_version"
                                )
                            ),
                        },
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            if capture is not None:
                try:
                    capture.stop()
                except Exception:
                    pass
                capture.cleanup()
            _run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "uninstall",
                    PACKAGE,
                ],
                timeout=60.0,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
