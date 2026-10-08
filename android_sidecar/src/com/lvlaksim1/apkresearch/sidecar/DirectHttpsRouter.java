package com.lvlaksim1.apkresearch.sidecar;

import android.os.Process;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
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
 * Rooted Android-side TCP router used only inside AVD-RESEARCH.
 *
 * Linux keeps the original destination for sockets delivered through TPROXY.
 * This process accepts those sockets, reads the preserved destination, reads
 * the first TLS record to recover SNI when available, opens an HTTP CONNECT
 * tunnel to the local HTTPS analyzer, and relays bytes in both directions.
 */
public final class DirectHttpsRouter {
    private static final int SOL_IP = 0;
    private static final int SOL_IPV6 = 41;
    private static final int IP_TRANSPARENT = 19;
    private static final int IPV6_TRANSPARENT = 75;
    private static final int IPV6_V6ONLY = 26;
    private static final int CONNECT_TIMEOUT_MS = 8000;
    private static final int MAX_CONNECT_HEADER = 16384;
    private static final int MAX_TLS_RECORD = 65540;
    private static final int BUFFER_SIZE = 32768;

    private DirectHttpsRouter() {
    }

    public static void main(String[] args) {
        int listenPortV4 = 0;
        int listenPortV6 = 0;
        int proxyPort = 0;
        try {
            for (int index = 0; index < args.length; index += 2) {
                if (index + 1 >= args.length) {
                    throw new IllegalArgumentException("missing argument value");
                }
                if ("--listen-port".equals(args[index])) {
                    listenPortV4 = parsePort(args[index + 1]);
                } else if ("--listen-port-v6".equals(args[index])) {
                    listenPortV6 = parsePort(args[index + 1]);
                } else if ("--proxy-port".equals(args[index])) {
                    proxyPort = parsePort(args[index + 1]);
                } else {
                    throw new IllegalArgumentException(
                            "unknown argument: " + args[index]);
                }
            }
            if (listenPortV4 == 0
                    || listenPortV6 == 0
                    || proxyPort == 0) {
                throw new IllegalArgumentException(
                        "usage: --listen-port <port> "
                                + "--listen-port-v6 <port> "
                                + "--proxy-port <port>");
            }
            run(listenPortV4, listenPortV6, proxyPort);
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

    private static void run(
            int listenPortV4,
            int listenPortV6,
            int proxyPort) throws Exception {
        FileDescriptor listenerV4 = null;
        FileDescriptor listenerV6 = null;
        try {
            listenerV4 = openListenerV4(listenPortV4);
            listenerV6 = openListenerV6(listenPortV6);

            final FileDescriptor finalListenerV4 = listenerV4;
            final FileDescriptor finalListenerV6 = listenerV6;
            AtomicInteger sequence = new AtomicInteger();

            Thread acceptV4 = new Thread(
                    () -> acceptLoop(
                            finalListenerV4,
                            proxyPort,
                            sequence,
                            "v4"),
                    "apk-research-direct-https-accept-v4");
            Thread acceptV6 = new Thread(
                    () -> acceptLoop(
                            finalListenerV6,
                            proxyPort,
                            sequence,
                            "v6"),
                    "apk-research-direct-https-accept-v6");
            acceptV4.setDaemon(true);
            acceptV6.setDaemon(true);
            acceptV4.start();
            acceptV6.start();

            System.out.println(
                    "READY "
                            + Process.myPid()
                            + " "
                            + listenPortV4
                            + " "
                            + listenPortV6);
            System.out.flush();

            try {
                acceptV4.join();
                acceptV6.join();
                throw new IOException(
                        "direct HTTPS router listener stopped");
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        } finally {
            closeFd(listenerV4);
            closeFd(listenerV6);
        }
    }

    private static FileDescriptor openListenerV4(
            int listenPort) throws Exception {
        FileDescriptor listener = Os.socket(
                OsConstants.AF_INET,
                OsConstants.SOCK_STREAM,
                OsConstants.IPPROTO_TCP);
        boolean success = false;
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
            success = true;
            return listener;
        } finally {
            if (!success) {
                closeFd(listener);
            }
        }
    }

    private static FileDescriptor openListenerV6(
            int listenPort) throws Exception {
        FileDescriptor listener = Os.socket(
                OsConstants.AF_INET6,
                OsConstants.SOCK_STREAM,
                OsConstants.IPPROTO_TCP);
        boolean success = false;
        try {
            Os.setsockoptInt(
                    listener,
                    OsConstants.SOL_SOCKET,
                    OsConstants.SO_REUSEADDR,
                    1);
            Os.setsockoptInt(
                    listener,
                    SOL_IPV6,
                    IPV6_V6ONLY,
                    1);
            Os.setsockoptInt(
                    listener,
                    SOL_IPV6,
                    IPV6_TRANSPARENT,
                    1);
            Os.bind(
                    listener,
                    java.net.InetAddress.getByName("::"),
                    listenPort);
            Os.listen(listener, 128);
            success = true;
            return listener;
        } finally {
            if (!success) {
                closeFd(listener);
            }
        }
    }

    private static void acceptLoop(
            FileDescriptor listener,
            int proxyPort,
            AtomicInteger sequence,
            String family) {
        while (true) {
            try {
                FileDescriptor client = Os.accept(
                        listener,
                        null);
                Thread worker = new Thread(
                        () -> handleClient(client, proxyPort),
                        "apk-research-direct-https-"
                                + family
                                + "-"
                                + sequence.incrementAndGet());
                worker.setDaemon(true);
                worker.start();
            } catch (Throwable error) {
                System.err.println(
                        "apk-research-direct-https-router-"
                                + family
                                + ": "
                                + error.getClass().getSimpleName()
                                + ": "
                                + String.valueOf(error.getMessage()));
                System.err.flush();
                return;
            }
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

            byte[] initialTls = readInitialTlsRecord(client);
            String serverName = parseTlsSni(initialTls);
            String destinationAuthority = authority(destination);
            String connectAuthority = (
                    serverName == null || serverName.isEmpty()
                    ? destinationAuthority
                    : serverName + ":" + destination.getPort()
            );

            System.err.println(
                    "route "
                            + destinationAuthority
                            + " via "
                            + connectAuthority);
            System.err.flush();

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

            String connect =
                    "CONNECT "
                            + connectAuthority
                            + " HTTP/1.1\r\nHost: "
                            + connectAuthority
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

            proxyOutput.write(initialTls);
            proxyOutput.flush();

            System.err.println(
                    "connected "
                            + connectAuthority);
            System.err.flush();

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
            System.err.flush();
            closePair(client, proxy, closed);
        }
    }

    private static byte[] readInitialTlsRecord(
            FileDescriptor source) throws Exception {
        byte[] header = new byte[5];
        readExact(source, header, 0, header.length);
        if ((header[0] & 0xff) != 22) {
            throw new IOException(
                    "direct TCP/443 stream did not start with TLS handshake");
        }
        int bodyLength =
                ((header[3] & 0xff) << 8)
                        | (header[4] & 0xff);
        int total = 5 + bodyLength;
        if (bodyLength <= 0 || total > MAX_TLS_RECORD) {
            throw new IOException(
                    "invalid initial TLS record length " + bodyLength);
        }
        byte[] record = new byte[total];
        System.arraycopy(
                header,
                0,
                record,
                0,
                header.length);
        readExact(
                source,
                record,
                header.length,
                bodyLength);
        return record;
    }

    private static void readExact(
            FileDescriptor source,
            byte[] data,
            int offset,
            int length) throws Exception {
        int position = offset;
        int remaining = length;
        while (remaining > 0) {
            int count = Os.read(
                    source,
                    data,
                    position,
                    remaining);
            if (count <= 0) {
                throw new IOException(
                        "direct TCP stream closed during TLS preface");
            }
            position += count;
            remaining -= count;
        }
    }

    private static String parseTlsSni(
            byte[] record) {
        try {
            int position = 5;
            if ((record[position++] & 0xff) != 1) {
                return null;
            }
            int handshakeLength =
                    ((record[position++] & 0xff) << 16)
                            | ((record[position++] & 0xff) << 8)
                            | (record[position++] & 0xff);
            int handshakeEnd = Math.min(
                    record.length,
                    position + handshakeLength);
            if (position + 34 > handshakeEnd) {
                return null;
            }

            position += 2;
            position += 32;

            int sessionLength = record[position++] & 0xff;
            position += sessionLength;
            if (position + 2 > handshakeEnd) {
                return null;
            }

            int cipherLength =
                    ((record[position++] & 0xff) << 8)
                            | (record[position++] & 0xff);
            position += cipherLength;
            if (position + 1 > handshakeEnd) {
                return null;
            }

            int compressionLength =
                    record[position++] & 0xff;
            position += compressionLength;
            if (position + 2 > handshakeEnd) {
                return null;
            }

            int extensionsLength =
                    ((record[position++] & 0xff) << 8)
                            | (record[position++] & 0xff);
            int extensionsEnd = Math.min(
                    handshakeEnd,
                    position + extensionsLength);

            while (position + 4 <= extensionsEnd) {
                int type =
                        ((record[position++] & 0xff) << 8)
                                | (record[position++] & 0xff);
                int length =
                        ((record[position++] & 0xff) << 8)
                                | (record[position++] & 0xff);
                int extensionEnd = position + length;
                if (extensionEnd > extensionsEnd) {
                    return null;
                }
                if (type == 0 && length >= 5) {
                    int listLength =
                            ((record[position] & 0xff) << 8)
                                    | (record[position + 1] & 0xff);
                    int item = position + 2;
                    int listEnd = Math.min(
                            extensionEnd,
                            item + listLength);
                    while (item + 3 <= listEnd) {
                        int nameType =
                                record[item++] & 0xff;
                        int nameLength =
                                ((record[item++] & 0xff) << 8)
                                        | (record[item++] & 0xff);
                        if (item + nameLength > listEnd) {
                            return null;
                        }
                        if (nameType == 0 && nameLength > 0) {
                            return new String(
                                    record,
                                    item,
                                    nameLength,
                                    StandardCharsets.US_ASCII);
                        }
                        item += nameLength;
                    }
                }
                position = extensionEnd;
            }
        } catch (RuntimeException ignored) {
            return null;
        }
        return null;
    }

    private static String authority(
            InetSocketAddress destination) {
        String host = destination.getAddress() != null
                ? destination.getAddress().getHostAddress()
                : destination.getHostString();
        int scope = host.indexOf('%');
        if (scope >= 0) {
            host = host.substring(0, scope);
        }
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
