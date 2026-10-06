package com.lvlaksim1.apkresearch.sidecar;

import android.hardware.display.VirtualDisplay;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.os.SystemClock;
import android.view.Surface;

import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Method;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

final class ScreenStreamer implements Runnable {
    static final int STREAM_VERSION = 1;
    static final byte[] MAGIC =
            "APKRSCRN".getBytes(StandardCharsets.US_ASCII);

    private static final int CONNECT_TIMEOUT_MS = 5000;
    private static final int DEQUEUE_TIMEOUT_US = 100000;
    private static final int FRAME_RATE = 30;
    private static final int I_FRAME_INTERVAL_SECONDS = 2;
    private static final long REPEAT_FRAME_DELAY_US = 100000L;

    private final int port;
    private final int width;
    private final int height;
    private final int bitRate;

    private final CountDownLatch started = new CountDownLatch(1);
    private final CountDownLatch done = new CountDownLatch(1);

    private volatile boolean stopRequested;
    private volatile String error;
    private volatile long packetCount;
    private volatile long byteCount;
    private volatile long firstPtsUs = -1L;
    private volatile long lastPtsUs = -1L;

    private Thread thread;

    ScreenStreamer(
            int port,
            int width,
            int height,
            int bitRate) {
        this.port = port;
        this.width = width;
        this.height = height;
        this.bitRate = bitRate;
    }

    void start() {
        thread = new Thread(this, "apk-research-screen-stream");
        thread.start();
    }

    boolean awaitStarted(
            long timeout,
            TimeUnit unit) throws InterruptedException {
        return started.await(timeout, unit);
    }

    boolean awaitDone(
            long timeout,
            TimeUnit unit) throws InterruptedException {
        return done.await(timeout, unit);
    }

    void requestStop() {
        stopRequested = true;
    }

    boolean isDone() {
        return done.getCount() == 0;
    }

    String getError() {
        return error;
    }

    long getPacketCount() {
        return packetCount;
    }

    long getByteCount() {
        return byteCount;
    }

    long getFirstPtsUs() {
        return firstPtsUs;
    }

    long getLastPtsUs() {
        return lastPtsUs;
    }

    @Override
    public void run() {
        Socket socket = null;
        DataOutputStream output = null;
        MediaCodec codec = null;
        Surface inputSurface = null;
        VirtualDisplay display = null;
        boolean codecStarted = false;

        try {
            socket = new Socket();
            socket.connect(
                    new InetSocketAddress("127.0.0.1", port),
                    CONNECT_TIMEOUT_MS);
            socket.setTcpNoDelay(true);
            output = new DataOutputStream(socket.getOutputStream());

            MediaFormat format = MediaFormat.createVideoFormat(
                    "video/avc",
                    width,
                    height);
            format.setInteger(
                    MediaFormat.KEY_COLOR_FORMAT,
                    MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
            format.setInteger(MediaFormat.KEY_BIT_RATE, bitRate);
            format.setInteger(MediaFormat.KEY_FRAME_RATE, FRAME_RATE);
            format.setInteger(
                    MediaFormat.KEY_I_FRAME_INTERVAL,
                    I_FRAME_INTERVAL_SECONDS);
            format.setInteger(MediaFormat.KEY_PRIORITY, 0);
            format.setInteger(MediaFormat.KEY_LATENCY, 1);
            format.setLong(
                    MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER,
                    REPEAT_FRAME_DELAY_US);

            codec = MediaCodec.createEncoderByType("video/avc");
            codec.configure(
                    format,
                    null,
                    null,
                    MediaCodec.CONFIGURE_FLAG_ENCODE);
            inputSurface = codec.createInputSurface();
            display = createMirrorDisplay(
                    width,
                    height,
                    inputSurface);
            codec.start();
            codecStarted = true;

            output.write(MAGIC);
            output.writeInt(STREAM_VERSION);
            output.writeInt(width);
            output.writeInt(height);
            output.writeInt(bitRate);
            output.writeLong(SystemClock.elapsedRealtimeNanos());
            output.flush();

            started.countDown();

            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            boolean eosRequested = false;
            boolean eosSeen = false;

            while (!eosSeen) {
                if (stopRequested && !eosRequested) {
                    codec.signalEndOfInputStream();
                    eosRequested = true;
                }

                int bufferId = codec.dequeueOutputBuffer(
                        info,
                        DEQUEUE_TIMEOUT_US);
                if (bufferId == MediaCodec.INFO_TRY_AGAIN_LATER) {
                    continue;
                }
                if (bufferId == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    continue;
                }
                if (bufferId < 0) {
                    continue;
                }

                try {
                    ByteBuffer buffer = codec.getOutputBuffer(bufferId);
                    if (buffer == null) {
                        throw new IOException("encoder output buffer is null");
                    }

                    int size = Math.max(0, info.size);
                    output.writeInt(info.flags);
                    output.writeLong(info.presentationTimeUs);
                    output.writeInt(size);

                    if (size > 0) {
                        ByteBuffer copy = buffer.duplicate();
                        copy.position(info.offset);
                        copy.limit(info.offset + size);
                        byte[] payload = new byte[size];
                        copy.get(payload);
                        output.write(payload);

                        packetCount += 1L;
                        byteCount += size;
                        if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
                            if (firstPtsUs < 0L) {
                                firstPtsUs = info.presentationTimeUs;
                            }
                            lastPtsUs = info.presentationTimeUs;
                        }
                    }
                    output.flush();

                    eosSeen =
                            (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                                    != 0;
                } finally {
                    codec.releaseOutputBuffer(bufferId, false);
                }
            }
        } catch (Exception exc) {
            error = exc.getClass().getSimpleName()
                    + ": "
                    + String.valueOf(exc.getMessage());
        } finally {
            started.countDown();

            if (display != null) {
                try {
                    display.release();
                } catch (Exception ignored) {
                }
            }
            if (codec != null) {
                if (codecStarted) {
                    try {
                        codec.stop();
                    } catch (Exception ignored) {
                    }
                }
                try {
                    codec.release();
                } catch (Exception ignored) {
                }
            }
            if (inputSurface != null) {
                try {
                    inputSurface.release();
                } catch (Exception ignored) {
                }
            }
            if (output != null) {
                try {
                    output.flush();
                } catch (Exception ignored) {
                }
            }
            if (socket != null) {
                try {
                    socket.close();
                } catch (Exception ignored) {
                }
            }
            done.countDown();
        }
    }

    private static VirtualDisplay createMirrorDisplay(
            int width,
            int height,
            Surface surface) throws Exception {
        Method method = android.hardware.display.DisplayManager.class.getMethod(
                "createVirtualDisplay",
                String.class,
                int.class,
                int.class,
                int.class,
                Surface.class);
        Object result = method.invoke(
                null,
                "apk-research-screen",
                width,
                height,
                0,
                surface);
        if (!(result instanceof VirtualDisplay)) {
            throw new IOException("display mirror creation returned no display");
        }
        return (VirtualDisplay) result;
    }
}
