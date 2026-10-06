package com.lvlaksim1.apkresearch.sidecar;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

public final class Agent {
    public static final int PROTOCOL_VERSION = 2;
    public static final String AGENT_VERSION = "0.2.0";
    private static final int CONNECT_TIMEOUT_MS = 5000;
    private static final int SCREEN_START_TIMEOUT_MS = 8000;
    private static final int SCREEN_STOP_TIMEOUT_MS = 8000;
    private static final int MAX_LINE_LENGTH = 4096;

    private Agent() {
    }

    public static void main(String[] args) {
        int exitCode = 0;
        try {
            int port = parsePort(args);
            run(port);
        } catch (Exception exc) {
            System.err.println("apk-research-agent: " + exc.getMessage());
            exitCode = 2;
        }
        if (exitCode != 0) {
            System.exit(exitCode);
        }
    }

    private static int parsePort(String[] args) {
        if (args.length != 2 || !"--port".equals(args[0])) {
            throw new IllegalArgumentException("usage: --port <1..65535>");
        }
        return parseInt(args[1], 1, 65535, "invalid port");
    }

    private static int parseInt(
            String value,
            int minimum,
            int maximum,
            String message) {
        int parsed;
        try {
            parsed = Integer.parseInt(value);
        } catch (NumberFormatException exc) {
            throw new IllegalArgumentException(message);
        }
        if (parsed < minimum || parsed > maximum) {
            throw new IllegalArgumentException(message);
        }
        return parsed;
    }

    private static void run(int port) throws IOException {
        Socket socket = new Socket();
        ScreenStreamer screen = null;
        try {
            socket.connect(
                    new InetSocketAddress("127.0.0.1", port),
                    CONNECT_TIMEOUT_MS);
            socket.setTcpNoDelay(true);

            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(
                            socket.getInputStream(),
                            StandardCharsets.UTF_8));
            BufferedWriter writer = new BufferedWriter(
                    new OutputStreamWriter(
                            socket.getOutputStream(),
                            StandardCharsets.UTF_8));

            writeLine(
                    writer,
                    "APK_RESEARCH_AGENT "
                            + PROTOCOL_VERSION
                            + " "
                            + AGENT_VERSION);

            String hello = readBoundedLine(reader);
            String expectedHello =
                    "HELLO "
                            + PROTOCOL_VERSION
                            + " "
                            + AGENT_VERSION;
            if (!expectedHello.equals(hello)) {
                writeLine(writer, "ERROR incompatible-handshake");
                throw new IOException("incompatible host handshake");
            }

            writeLine(
                    writer,
                    "READY "
                            + PROTOCOL_VERSION
                            + " "
                            + AGENT_VERSION);

            while (true) {
                String line = readBoundedLine(reader);
                if (line == null) {
                    stopScreenQuietly(screen);
                    return;
                }
                if ("STOP".equals(line)) {
                    stopScreenQuietly(screen);
                    writeLine(writer, "BYE");
                    return;
                }
                if (line.startsWith("PING ")) {
                    String token = line.substring(5);
                    if (!isSafeToken(token)) {
                        writeLine(writer, "ERROR invalid-token");
                        continue;
                    }
                    long uptimeMillis = android.os.SystemClock.uptimeMillis();
                    writeLine(
                            writer,
                            "PONG " + token + " " + uptimeMillis);
                    continue;
                }
                if (line.startsWith("SCREEN_START ")) {
                    if (screen != null && !screen.isDone()) {
                        writeLine(writer, "ERROR screen-already-running");
                        continue;
                    }
                    String[] parts = line.split(" ");
                    if (parts.length != 5) {
                        writeLine(writer, "ERROR invalid-screen-start");
                        continue;
                    }
                    try {
                        int mediaPort = parseInt(
                                parts[1], 1, 65535, "invalid media port");
                        int width = parseInt(
                                parts[2], 64, 4096, "invalid screen width");
                        int height = parseInt(
                                parts[3], 64, 4096, "invalid screen height");
                        int bitRate = parseInt(
                                parts[4], 100000, 50000000, "invalid bit rate");

                        ScreenStreamer candidate = new ScreenStreamer(
                                mediaPort,
                                width,
                                height,
                                bitRate);
                        candidate.start();
                        if (!candidate.awaitStarted(
                                SCREEN_START_TIMEOUT_MS,
                                TimeUnit.MILLISECONDS)) {
                            candidate.requestStop();
                            candidate.awaitDone(
                                    SCREEN_STOP_TIMEOUT_MS,
                                    TimeUnit.MILLISECONDS);
                            writeLine(writer, "ERROR screen-start-timeout");
                            continue;
                        }
                        String error = candidate.getError();
                        if (error != null) {
                            candidate.requestStop();
                            candidate.awaitDone(
                                    SCREEN_STOP_TIMEOUT_MS,
                                    TimeUnit.MILLISECONDS);
                            writeLine(writer, "ERROR screen-start-failed");
                            continue;
                        }
                        screen = candidate;
                        writeLine(
                                writer,
                                "SCREEN_STARTED "
                                        + width
                                        + " "
                                        + height
                                        + " h264");
                    } catch (IllegalArgumentException exc) {
                        writeLine(writer, "ERROR invalid-screen-start");
                    } catch (InterruptedException exc) {
                        Thread.currentThread().interrupt();
                        writeLine(writer, "ERROR screen-start-interrupted");
                    }
                    continue;
                }
                if ("SCREEN_STOP".equals(line)) {
                    if (screen == null) {
                        writeLine(writer, "ERROR screen-not-running");
                        continue;
                    }
                    screen.requestStop();
                    try {
                        if (!screen.awaitDone(
                                SCREEN_STOP_TIMEOUT_MS,
                                TimeUnit.MILLISECONDS)) {
                            writeLine(writer, "ERROR screen-stop-timeout");
                            continue;
                        }
                    } catch (InterruptedException exc) {
                        Thread.currentThread().interrupt();
                        writeLine(writer, "ERROR screen-stop-interrupted");
                        continue;
                    }

                    String error = screen.getError();
                    if (error != null) {
                        writeLine(writer, "ERROR screen-stream-failed");
                        screen = null;
                        continue;
                    }

                    writeLine(
                            writer,
                            "SCREEN_STOPPED "
                                    + screen.getPacketCount()
                                    + " "
                                    + screen.getByteCount()
                                    + " "
                                    + screen.getFirstPtsUs()
                                    + " "
                                    + screen.getLastPtsUs());
                    screen = null;
                    continue;
                }
                writeLine(writer, "ERROR unknown-command");
            }
        } finally {
            stopScreenQuietly(screen);
            socket.close();
        }
    }

    private static void stopScreenQuietly(ScreenStreamer screen) {
        if (screen == null) {
            return;
        }
        screen.requestStop();
        try {
            screen.awaitDone(
                    SCREEN_STOP_TIMEOUT_MS,
                    TimeUnit.MILLISECONDS);
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
        }
    }

    private static String readBoundedLine(
            BufferedReader reader) throws IOException {
        StringBuilder value = new StringBuilder();
        while (true) {
            int next = reader.read();
            if (next == -1) {
                return value.length() == 0 ? null : value.toString();
            }
            if (next == '\n') {
                return value.toString();
            }
            if (next == '\r') {
                continue;
            }
            value.append((char) next);
            if (value.length() > MAX_LINE_LENGTH) {
                throw new IOException("protocol line too long");
            }
        }
    }

    private static boolean isSafeToken(String value) {
        if (value.length() < 1 || value.length() > 64) {
            return false;
        }
        for (int index = 0; index < value.length(); index++) {
            char c = value.charAt(index);
            boolean safe =
                    (c >= 'a' && c <= 'z')
                            || (c >= 'A' && c <= 'Z')
                            || (c >= '0' && c <= '9')
                            || c == '.'
                            || c == '_'
                            || c == '-';
            if (!safe) {
                return false;
            }
        }
        return true;
    }

    private static void writeLine(
            BufferedWriter writer,
            String value) throws IOException {
        writer.write(value);
        writer.write("\n");
        writer.flush();
    }
}
