package com.lvlaksim1.apkresearch.sidecar;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

public final class Agent {
    public static final int PROTOCOL_VERSION = 1;
    public static final String AGENT_VERSION = "0.1.0";
    private static final int CONNECT_TIMEOUT_MS = 5000;
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
        int port;
        try {
            port = Integer.parseInt(args[1]);
        } catch (NumberFormatException exc) {
            throw new IllegalArgumentException("invalid port");
        }
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("invalid port");
        }
        return port;
    }

    private static void run(int port) throws IOException {
        Socket socket = new Socket();
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
                    return;
                }
                if ("STOP".equals(line)) {
                    writeLine(writer, "BYE");
                    return;
                }
                if (line.startsWith("PING ")) {
                    String token = line.substring(5);
                    if (!isSafeToken(token)) {
                        writeLine(writer, "ERROR invalid-token");
                        continue;
                    }
                    long uptimeMillis = System.nanoTime() / 1_000_000L;
                    writeLine(
                            writer,
                            "PONG " + token + " " + uptimeMillis);
                    continue;
                }
                writeLine(writer, "ERROR unknown-command");
            }
        } finally {
            socket.close();
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
