package com.lvlaksim1.apkresearch.sidecar;

import android.os.Process;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.FileDescriptor;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Small rooted Android-side TCP router used only inside AVD-RESEARCH.
 *
 * The kernel keeps the original destination with TPROXY. This process accepts
 * the redirected TCP socket, reads that destination with getsockname(), opens
 * an HTTP CONNECT tunnel to the already configured local HTTPS analyzer, and
 * then relays bytes in both directions.
 */
public final class DirectHttpsRouter {
    private static final int SOL_IP = 0;
    private static final int IP_TRANSPARENT = 19;
    private static final int CONNECT_TIMEOUT_MS = 8000;
    private static final int MAX_CONNECT_HEADER = 16384;
    private static final int BUFFER_SIZE = 32768;

    private DirectHttpsRouter() {
    }

    public static void main(String[] args) {
        int listenPort = 0;
        int proxyPort = 0;
        try {
            for (int index = 0; index < args.length; index += 2) {
                if (index + 1 >= args.length) {
                    throw new IllegalArgumentException("missing argument value");
                }
                if ("--listen-port".equals(args[index])) {
                    listenPort = parsePort(args[index + 1]);
                } else if ("--proxy-port".equals(args[index])) {
                    proxyPort = parsePort(args[index + 1]);
                } else {
                    throw new IllegalArgumentException(
                            "unknown argument: " + args[index]);
                }
            }
            if (listenPort == 0 || proxyPort == 0) {
                throw new IllegalArgumentException(
                        "usage: --listen-port <port> --proxy-port <port>");
            }
            run(listenPort, proxyPort);
        } catch (Throwable error) {
            System.err.println(
                    "apk-research-direct-https-router: "
                            + error.getClass().getSimpleName()
                            + ": "
                            + String.valueOf(error.getMessage()));
            System.exit(2);
        }
    }

    private static int parsePort(String value) {
        int port;
        try {
            port = Integer.parseInt(value);
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException("invalid port");
        }
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("invalid port");
        }
        return port;
    }

    private static void run(int listenPort, int proxyPort)
            throws Exception {
        FileDescriptor listener = Os.socket(
                OsConstants.AF_INET,
                OsConstants.SOCK_STREAM,
                OsConstants.IPPROTO_TCP);
        try {
            Os.setsockoptInt(
                    listener,
                    OsConstants.SOL_SOCKET,
                    OsConstants.SO_REUSEADDR,
                    1);
            Os.setsockoptInt(
                    listener,
                    SOL_IP,
                    IP_TRANSPARENT,
                    1);
            Os.bind(
                    listener,
                    java.net.InetAddress.getByName("0.0.0.0"),
                    listenPort);
            Os.listen(listener, 128);

            System.out.println(
                    "READY " + Process.myPid() + " " + listenPort);
            System.out.flush();

            AtomicInteger sequence = new AtomicInteger();
            while (true) {
                FileDescriptor client = Os.accept(
                        listener,
                        null);
                Thread worker = new Thread(
                        () -> handleClient(client, proxyPort),
                        "apk-research-direct-https-"
                                + sequence.incrementAndGet());
                worker.setDaemon(true);
                worker.start();
            }
        } finally {
            closeFd(listener);
        }
    }

    private static void handleClient(
            FileDescriptor client,
            int proxyPort) {
        Socket proxy = null;
        AtomicBoolean closed = new AtomicBoolean();
        try {
            SocketAddress local = Os.getsockname(client);
            if (!(local instanceof InetSocketAddress)) {
                throw new IOException(
                        "original destination is not an INET socket");
            }
            InetSocketAddress destination =
                    (InetSocketAddress) local;
            if (destination.getPort() != 443) {
                throw new IOException(
                        "unexpected destination port "
                                + destination.getPort());
            }

            proxy = new Socket();
            proxy.setTcpNoDelay(true);
            proxy.connect(
                    new InetSocketAddress(
                            "127.0.0.1",
                            proxyPort),
                    CONNECT_TIMEOUT_MS);

            BufferedInputStream proxyInput =
                    new BufferedInputStream(
                            proxy.getInputStream());
            BufferedOutputStream proxyOutput =
                    new BufferedOutputStream(
                            proxy.getOutputStream());

            String authority = authority(destination);
            String connect =
                    "CONNECT "
                            + authority
                            + " HTTP/1.1\r\nHost: "
                            + authority
                            + "\r\nProxy-Connection: keep-alive\r\n\r\n";
            proxyOutput.write(
                    connect.getBytes(
                            StandardCharsets.ISO_8859_1));
            proxyOutput.flush();

            String responseHeader =
                    readConnectResponse(proxyInput);
            String firstLine = responseHeader;
            int lineEnd = responseHeader.indexOf("\r\n");
            if (lineEnd >= 0) {
                firstLine = responseHeader.substring(
                        0,
                        lineEnd);
            }
            if (!firstLine.contains(" 200 ")) {
                throw new IOException(
                        "local HTTPS analyzer rejected CONNECT: "
                                + firstLine);
            }

            final Socket relayProxy = proxy;
            Thread upload = new Thread(
                    () -> {
                        try {
                            pumpDeviceToProxy(
                                    client,
                                    relayProxy.getOutputStream());
                        } catch (Throwable ignored) {
                        } finally {
                            closePair(
                                    client,
                                    relayProxy,
                                    closed);
                        }
                    },
                    "apk-research-direct-https-up");
            Thread download = new Thread(
                    () -> {
                        try {
                            pumpProxyToDevice(
                                    relayProxy.getInputStream(),
                                    client);
                        } catch (Throwable ignored) {
                        } finally {
                            closePair(
                                    client,
                                    relayProxy,
                                    closed);
                        }
                    },
                    "apk-research-direct-https-down");
            upload.setDaemon(true);
            download.setDaemon(true);
            upload.start();
            download.start();
        } catch (Throwable error) {
            System.err.println(
                    "apk-research-direct-https-router-client: "
                            + error.getClass().getSimpleName()
                            + ": "
                            + String.valueOf(error.getMessage()));
            closePair(client, proxy, closed);
        }
    }

    private static String authority(
            InetSocketAddress destination) {
        String host = destination.getAddress() != null
                ? destination.getAddress().getHostAddress()
                : destination.getHostString();
        if (host.indexOf(':') >= 0
                && !host.startsWith("[")) {
            host = "[" + host + "]";
        }
        return host + ":" + destination.getPort();
    }

    private static String readConnectResponse(
            InputStream input) throws IOException {
        byte[] data = new byte[MAX_CONNECT_HEADER];
        int count = 0;
        int state = 0;
        while (count < data.length) {
            int value = input.read();
            if (value < 0) {
                throw new IOException(
                        "local HTTPS analyzer closed CONNECT response");
            }
            data[count++] = (byte) value;
            if (state == 0 && value == '\r') {
                state = 1;
            } else if (state == 1 && value == '\n') {
                state = 2;
            } else if (state == 2 && value == '\r') {
                state = 3;
            } else if (state == 3 && value == '\n') {
                return new String(
                        data,
                        0,
                        count,
                        StandardCharsets.ISO_8859_1);
            } else {
                state = value == '\r' ? 1 : 0;
            }
        }
        throw new IOException(
                "CONNECT response header exceeded limit");
    }

    private static void pumpDeviceToProxy(
            FileDescriptor source,
            OutputStream target) throws Exception {
        byte[] buffer = new byte[BUFFER_SIZE];
        while (true) {
            int count = Os.read(
                    source,
                    buffer,
                    0,
                    buffer.length);
            if (count <= 0) {
                return;
            }
            target.write(
                    buffer,
                    0,
                    count);
            target.flush();
        }
    }

    private static void pumpProxyToDevice(
            InputStream source,
            FileDescriptor target) throws Exception {
        byte[] buffer = new byte[BUFFER_SIZE];
        while (true) {
            int count = source.read(buffer);
            if (count < 0) {
                return;
            }
            int offset = 0;
            while (offset < count) {
                int written = Os.write(
                        target,
                        buffer,
                        offset,
                        count - offset);
                if (written <= 0) {
                    throw new IOException(
                            "unable to write routed HTTPS bytes");
                }
                offset += written;
            }
        }
    }

    private static void closePair(
            FileDescriptor client,
            Socket proxy,
            AtomicBoolean closed) {
        if (!closed.compareAndSet(false, true)) {
            return;
        }
        closeFd(client);
        if (proxy != null) {
            try {
                proxy.close();
            } catch (IOException ignored) {
            }
        }
    }

    private static void closeFd(FileDescriptor fd) {
        if (fd == null || !fd.valid()) {
            return;
        }
        try {
            Os.close(fd);
        } catch (ErrnoException ignored) {
        }
    }
}
