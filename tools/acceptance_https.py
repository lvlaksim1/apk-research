from __future__ import annotations

import json
import os
import shutil
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


def _build_apk(root: Path) -> Path:
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
import java.net.URL;
import java.net.Proxy;
import javax.net.ssl.HttpsURLConnection;

public final class MainActivity extends Activity {{
    @Override
    public void onCreate(Bundle state) {{
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("HTTPS probe started");
        setContentView(view);
        new Thread(() -> {{
            try {{
                StringBuilder report = new StringBuilder();
                for (int attempt = 0; attempt < 2; attempt++) {{
                    String route = attempt == 0 ? "system" : "direct";
                    URL url = new URL("{TARGET_URL}");
                    HttpsURLConnection connection = (HttpsURLConnection)
                        (attempt == 0
                            ? url.openConnection()
                            : url.openConnection(Proxy.NO_PROXY));
                    connection.setConnectTimeout(15000);
                    connection.setReadTimeout(15000);
                    connection.setRequestProperty("X-Apk-Research-Mode", route);
                    int code = connection.getResponseCode();
                    InputStream stream = code >= 400
                        ? connection.getErrorStream()
                        : connection.getInputStream();
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    if (stream != null) {{
                        byte[] buffer = new byte[4096];
                        int count;
                        while ((count = stream.read(buffer)) >= 0) {{
                            out.write(buffer, 0, count);
                        }}
                        stream.close();
                    }}
                    report.append(route).append(":").append(code)
                        .append(" bytes=").append(out.size()).append(" ");
                    connection.disconnect();
                }}
                runOnUiThread(() -> view.setText(report.toString()));
            }} catch (Exception error) {{
                runOnUiThread(
                    () -> view.setText("HTTPS ERROR " + error.toString())
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
        apk = _build_apk(root)
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
                        **started.to_dict(),
                    },
                    ensure_ascii=False,
                )
            )

            deadline = time.monotonic() + 60.0
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
                    if (
                        TARGET_URL in text
                        and '"X-Apk-Research-Mode"' in text
                        and '"direct"' in text
                    ):
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

            transactions = _read_transactions(
                Path(result.archive)
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
            modes = set()
            response_sizes = {}
            for transaction in matches:
                headers = (
                    transaction.get("request") or {}
                ).get("headers") or []
                mode = next(
                    (
                        str(value)
                        for name, value in headers
                        if str(name).lower() == "x-apk-research-mode"
                    ),
                    None,
                )
                if mode not in {"system", "direct"}:
                    continue
                modes.add(mode)
                if mode == "direct" and (
                    (transaction.get("interception") or {}).get("route") != "direct"
                ):
                    raise RuntimeError("Direct HTTPS flow has no confirmed route")
                response = transaction.get("response") or {}
                body = response.get("body") or {}
                if not (transaction.get("interception") or {}).get(
                    "tls_decrypted"
                ):
                    raise RuntimeError(
                        f"HTTPS analyzer did not read the {mode} TLS flow"
                    )
                if int(response.get("status_code") or 0) != 200:
                    raise RuntimeError(
                        f"HTTPS {mode} status was not 200: {response}"
                    )
                if int(body.get("size") or 0) <= 0:
                    raise RuntimeError(
                        f"HTTPS {mode} response body is empty"
                    )
                response_sizes[mode] = int(body["size"])
            if modes != {"system", "direct"}:
                raise RuntimeError(
                    "Expected both system and direct HTTPS transactions, "
                    + f"observed={sorted(modes)}"
                )
            transaction = matches[-1]
            response = transaction.get("response") or {}
            body = response.get("body") or {}
            with zipfile.ZipFile(Path(result.archive)) as evidence:
                route_log = evidence.read(
                    "01_raw/network/https-direct-route.log"
                ).decode("utf-8", errors="replace")
                if "CONNECTION_ROUTED destination=" not in route_log:
                    raise RuntimeError(
                        "Android routing log does not confirm direct TCP/443"
                    )
                for required in (
                    "02_normalized/dns.jsonl",
                    "02_normalized/tls-sessions.jsonl",
                    "02_normalized/action-network-links.jsonl",
                    "02_normalized/screen-timing.jsonl",
                    "02_normalized/network-enrichment.json",
                ):
                    if required not in evidence.namelist():
                        raise RuntimeError(
                            "Missing required derived evidence file: " + required
                        )
                enrichment = json.loads(evidence.read(
                    "02_normalized/network-enrichment.json"
                ))
                if enrichment.get("status") != "complete":
                    raise RuntimeError(
                        "Network enrichment incomplete: " + str(enrichment)
                    )
                if int(
                    (enrichment.get("counts") or {}).get("http_transactions") or 0
                ) < 2:
                    raise RuntimeError(
                        "Network enrichment omitted actual HTTP transactions"
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
                        "verified_routes": sorted(modes),
                        "route_response_sizes": response_sizes,
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
