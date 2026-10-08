from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from apk_research.orchestrator import ResearchOrchestrator
from apk_research.targets import AdbClient


SERIAL = "emulator-5554"
PACKAGE = "org.apkresearch.httpsacceptance"
STOREPASS = "changeit"
TARGET_URL = "https://example.com/"
OUTPUT_ROOT = Path("acceptance-output").resolve()
SESSION_ROOT = OUTPUT_ROOT / "https-sessions"
ARCHIVE = OUTPUT_ROOT / "https-acceptance.research.zip"


def _sdk_root() -> Path:
    value = os.environ.get("ANDROID_HOME") or os.environ.get(
        "ANDROID_SDK_ROOT"
    )
    if not value:
        raise RuntimeError(
            "ANDROID_HOME/ANDROID_SDK_ROOT is not set"
        )
    return Path(value).resolve()


def _newest_build_tools(root: Path) -> Path:
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
            + "\n"
            + result.stdout
            + "\n"
            + result.stderr
        )
    return result


def _run_d8(
    d8: Path,
    arguments: list[str],
) -> None:
    command = [str(d8), *arguments]
    if os.name == "nt" and d8.suffix.lower() in {
        ".bat",
        ".cmd",
    }:
        command = [
            os.environ.get("COMSPEC") or "cmd.exe",
            "/d",
            "/s",
            "/c",
            subprocess.list2cmdline(
                [str(d8), *arguments]
            ),
        ]
    _run(command)


def _build_apk(
    root: Path,
    target_ipv4: str,
) -> Path:
    sdk = _sdk_root()
    build_tools = _newest_build_tools(sdk)
    android_jar = (
        sdk
        / "platforms"
        / "android-35"
        / "android.jar"
    )
    aapt2 = build_tools / "aapt2"
    d8 = build_tools / "d8"
    zipalign = build_tools / "zipalign"
    apksigner = build_tools / "apksigner"
    javac = shutil.which("javac")
    keytool = shutil.which("keytool")

    for tool in (
        android_jar,
        aapt2,
        d8,
        zipalign,
        apksigner,
    ):
        if not tool.is_file():
            raise RuntimeError(
                f"Required Android tool is missing: {tool}"
            )
    if not javac or not keytool:
        raise RuntimeError(
            "javac/keytool is missing"
        )

    manifest = root / "AndroidManifest.xml"
    manifest.write_text(
        """<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.apkresearch.httpsacceptance"
    android:versionCode="1"
    android:versionName="1.0">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35" />
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:label="HTTPS Acceptance"
        android:usesCleartextTraffic="false"
        android:theme="@android:style/Theme.Material.Light.NoActionBar">
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
        parents=True,
        exist_ok=True,
    )
    source = source_dir / "MainActivity.java"
    source.write_text(
        f"""package org.apkresearch.httpsacceptance;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import javax.net.ssl.SNIHostName;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

public final class MainActivity extends Activity {{
    @Override
    public void onCreate(Bundle state) {{
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("HTTPS probe started");
        setContentView(view);
        new Thread(() -> {{
            try {{
                SSLSocket socket = (SSLSocket)
                    SSLSocketFactory.getDefault().createSocket();
                socket.connect(
                    new InetSocketAddress("{target_ipv4}", 443),
                    15000);
                socket.setSoTimeout(15000);

                SSLParameters parameters =
                    socket.getSSLParameters();
                parameters.setServerNames(
                    Collections.singletonList(
                        new SNIHostName("example.com")));
                parameters.setEndpointIdentificationAlgorithm(
                    "HTTPS");
                socket.setSSLParameters(parameters);
                socket.startHandshake();

                OutputStream output = socket.getOutputStream();
                String request =
                    "GET / HTTP/1.1\\r\\n"
                    + "Host: example.com\\r\\n"
                    + "Connection: close\\r\\n"
                    + "X-Apk-Research-Acceptance: "
                    + "v0.30.1-direct\\r\\n\\r\\n";
                output.write(
                    request.getBytes(
                        StandardCharsets.ISO_8859_1));
                output.flush();

                InputStream stream = socket.getInputStream();
                ByteArrayOutputStream out =
                    new ByteArrayOutputStream();
                byte[] buffer = new byte[4096];
                int count;
                while ((count = stream.read(buffer)) >= 0) {{
                    out.write(buffer, 0, count);
                }}
                stream.close();
                socket.close();

                String rawResponse =
                    new String(
                        out.toByteArray(),
                        StandardCharsets.ISO_8859_1);
                int code =
                    rawResponse.startsWith("HTTP/1.1 200")
                    || rawResponse.startsWith("HTTP/1.0 200")
                    ? 200
                    : 0;
                String result =
                    "HTTPS " + code + " bytes=" + out.size();
                runOnUiThread(() -> view.setText(result));
            }} catch (Exception error) {{
                runOnUiThread(
                    () -> view.setText(
                        "HTTPS ERROR " + error.toString()
                    )
                );
            }}
        }}).start();
    }}
}}
""",
        encoding="utf-8",
    )

    classes = root / "classes"
    dex = root / "dex"
    classes.mkdir()
    dex.mkdir()
    _run(
        [
            javac,
            "-encoding",
            "UTF-8",
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
    class_files = [
        str(path)
        for path in classes.rglob("*.class")
    ]
    _run_d8(
        d8,
        [
            "--lib",
            str(android_jar),
            "--min-api",
            "23",
            "--output",
            str(dex),
            *class_files,
        ],
    )

    unsigned = root / "unsigned.apk"
    with_dex = root / "with-dex.apk"
    aligned = root / "aligned.apk"
    signed = root / "https-acceptance.apk"
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
    shutil.copy2(
        unsigned,
        with_dex,
    )
    with zipfile.ZipFile(
        with_dex,
        "a",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(
            dex / "classes.dex",
            "classes.dex",
        )
    _run(
        [
            str(zipalign),
            "-f",
            "4",
            str(with_dex),
            str(aligned),
        ]
    )
    _run(
        [
            keytool,
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
            str(signed),
            str(aligned),
        ]
    )
    return signed


def _read_interception_metadata(
    archive_path: Path,
) -> dict:
    with zipfile.ZipFile(
        archive_path
    ) as archive:
        return json.loads(
            archive.read(
                "02_normalized/http-interception.json"
            ).decode(
                "utf-8",
                errors="replace",
            )
        )


def _read_transactions(
    archive_path: Path,
) -> list[dict]:
    with zipfile.ZipFile(
        archive_path
    ) as archive:
        raw = archive.read(
            "02_normalized/http-transactions.jsonl"
        ).decode(
            "utf-8",
            errors="replace",
        )
    return [
        json.loads(line)
        for line in raw.splitlines()
        if line.strip()
    ]


def main() -> int:
    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )
    client = AdbClient.from_environment()
    sdk = _sdk_root()
    adb = sdk / "platform-tools" / "adb"

    with tempfile.TemporaryDirectory(
        prefix="apk-research-https-acceptance-"
    ) as raw:
        root = Path(raw)
        addresses = sorted(
            {
                str(item[4][0])
                for item in socket.getaddrinfo(
                    "example.com",
                    443,
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                )
            }
        )
        if not addresses:
            raise RuntimeError(
                "No IPv4 address resolved for example.com"
            )
        target_ipv4 = addresses[0]
        apk = _build_apk(
            root,
            target_ipv4,
        )
        try:
            _run(
                [
                    str(adb),
                    "-s",
                    SERIAL,
                    "install",
                    "-r",
                    "-t",
                    "-g",
                    str(apk),
                ],
                timeout=180.0,
            )

            orchestrator = ResearchOrchestrator(
                client,
                SERIAL,
                PACKAGE,
                runtime_root=SESSION_ROOT,
                output_path=ARCHIVE,
                overwrite_output=True,
                screen_chunk_seconds=30,
                launch_mode="clean",
            )
            started = orchestrator.start()
            print(
                json.dumps(
                    {
                        "event": "https_acceptance_started",
                        "direct_target_ipv4": target_ipv4,
                        **started.to_dict(),
                    },
                    ensure_ascii=False,
                )
            )

            deadline = time.monotonic() + 25.0
            session = orchestrator.session
            if session is None:
                raise RuntimeError(
                    "HTTPS acceptance session is missing"
                )
            transactions_path = (
                session.paths.root
                / "02_normalized/http-transactions.jsonl"
            )
            while time.monotonic() < deadline:
                if (
                    transactions_path.is_file()
                    and transactions_path.stat().st_size > 0
                ):
                    text = transactions_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                    if TARGET_URL in text:
                        break
                time.sleep(0.5)

            health = orchestrator.health_check()
            if not health.healthy:
                raise RuntimeError(
                    "HTTPS acceptance collector health degraded: "
                    + json.dumps(
                        health.to_dict()
                    )
                )
            result = orchestrator.stop_and_export()
            if result.session_status != "complete":
                raise RuntimeError(
                    "HTTPS acceptance did not finish complete: "
                    + result.session_status
                )

            archive_path = Path(result.archive)
            metadata = _read_interception_metadata(
                archive_path
            )
            routing = (
                metadata.get("direct_https_routing")
                or {}
            )
            if not routing.get("enabled"):
                raise RuntimeError(
                    "Direct HTTPS routing was not active"
                )
            transactions = _read_transactions(
                archive_path
            )
            matches = [
                item
                for item in transactions
                if str(item.get("url") or "")
                == TARGET_URL
            ]
            if not matches:
                raise RuntimeError(
                    "No decrypted HTTPS transaction was captured "
                    f"for {TARGET_URL}"
                )
            transaction = matches[-1]
            interception = (
                transaction.get("interception")
                or {}
            )
            response = (
                transaction.get("response")
                or {}
            )
            body = response.get("body") or {}
            if not interception.get(
                "tls_decrypted"
            ):
                raise RuntimeError(
                    "HTTPS transaction was not marked decrypted"
                )
            if int(
                response.get(
                    "status_code"
                )
                or 0
            ) != 200:
                raise RuntimeError(
                    "Unexpected HTTPS status: "
                    + str(
                        response.get(
                            "status_code"
                        )
                    )
                )
            if int(body.get("size") or 0) <= 0:
                raise RuntimeError(
                    "HTTPS response body is empty"
                )

            print(
                json.dumps(
                    {
                        "event": "https_acceptance",
                        "status": "ok",
                        "url": transaction.get("url"),
                        "http_version": (
                            response.get("http_version")
                            or transaction.get(
                                "http_version"
                            )
                        ),
                        "response_bytes": body.get(
                            "size"
                        ),
                        "direct_https_routing": True,
                        "direct_target_ipv4": target_ipv4,
                        "archive": result.archive,
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
