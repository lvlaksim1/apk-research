/*
 * apk-research: Android-local HTTPS route transport.
 *
 * Linux/Android netfilter supplies the original TCP destination of
 * connections from the selected Android application. The transport
 * opens an ordinary HTTP CONNECT tunnel to the existing local analyzer.
 * It does not retain TLS content; the application-level analyzer owns
 * any readable HTTPS transactions.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>

#ifndef SO_ORIGINAL_DST
#define SO_ORIGINAL_DST 80
#endif
#define ROUTE_BACKLOG 32
#define ROUTE_MAX_WORKERS 128
#define ROUTE_IO_BUFFER 16384
#define ROUTE_HANDSHAKE_MAX 8192

static volatile sig_atomic_t running = 1;
static volatile int workers = 0;
static int log_fd = -1;
static int server_fd = -1;
static int upstream_port = 0;

static void route_log(const char *format, ...) {
    char line[600];
    va_list args;
    va_start(args, format);
    int n = vsnprintf(line, sizeof(line) - 2, format, args);
    va_end(args);
    if (n < 0 || log_fd < 0) return;
    size_t used = (size_t)n;
    if (used > sizeof(line) - 2) used = sizeof(line) - 2;
    line[used++] = '\n';
    (void)write(log_fd, line, used);
}

static void stop_requested(int signal_number) {
    (void)signal_number;
    running = 0;
    if (server_fd >= 0) close(server_fd);
}

static int write_all(int fd, const void *data, size_t size) {
    const uint8_t *cursor = (const uint8_t *)data;
    while (size > 0) {
        ssize_t n = send(fd, cursor, size, MSG_NOSIGNAL);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        cursor += (size_t)n;
        size -= (size_t)n;
    }
    return 0;
}

static int connect_local_analyzer(void) {
    int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0) return -1;
    struct sockaddr_in local = {0};
    local.sin_family = AF_INET;
    local.sin_port = htons((uint16_t)upstream_port);
    local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (connect(fd, (struct sockaddr *)&local, sizeof(local)) != 0) {
        close(fd);
        return -1;
    }
    struct timeval timeout = { .tv_sec = 12, .tv_usec = 0 };
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    return fd;
}

static int accept_connect_response(int fd) {
    char response[ROUTE_HANDSHAKE_MAX + 1];
    size_t count = 0;
    while (count < ROUTE_HANDSHAKE_MAX) {
        char c = 0;
        ssize_t n = recv(fd, &c, 1, 0);
        if (n <= 0) return -1;
        response[count++] = c;
        if (count >= 4 &&
            memcmp(response + count - 4, "\r\n\r\n", 4) == 0) {
            response[count] = 0;
            if (strncmp(response, "HTTP/1.1 200", 12) == 0 ||
                strncmp(response, "HTTP/1.0 200", 12) == 0) return 0;
            return -1;
        }
    }
    return -1;
}

static void copy_both_ways(int client, int upstream) {
    struct pollfd streams[2] = {
        {.fd=client, .events=POLLIN},
        {.fd=upstream, .events=POLLIN},
    };
    char data[ROUTE_IO_BUFFER];
    while (running) {
        int rc = poll(streams, 2, 1000);
        if (rc < 0 && errno == EINTR) continue;
        if (rc < 0) break;
        if (rc == 0) continue;
        for (int i = 0; i < 2; i++) {
            if (streams[i].revents & (POLLERR | POLLHUP | POLLNVAL)) return;
            if (!(streams[i].revents & POLLIN)) continue;
            ssize_t n = recv(streams[i].fd, data, sizeof(data), 0);
            if (n <= 0) return;
            if (write_all(streams[1-i].fd, data, (size_t)n) != 0) return;
        }
    }
}

static void *handle_connection(void *opaque) {
    int client = (int)(intptr_t)opaque;
    int upstream = -1;
    struct sockaddr_in original = {0};
    socklen_t length = sizeof(original);
    if (getsockopt(client, SOL_IP, SO_ORIGINAL_DST, &original, &length) != 0 ||
        original.sin_family != AF_INET) {
        route_log("CONNECTION_ERROR reason=original_destination errno=%d", errno);
        goto done;
    }
    char address[INET_ADDRSTRLEN];
    if (!inet_ntop(AF_INET, &original.sin_addr, address, sizeof(address)))
        goto done;
    unsigned port = (unsigned)ntohs(original.sin_port);
    if ((ntohl(original.sin_addr.s_addr) >> 24) == 127) {
        route_log("CONNECTION_SKIP original_loopback=%s:%u", address, port);
        goto done;
    }
    upstream = connect_local_analyzer();
    if (upstream < 0) {
        route_log("CONNECTION_ERROR reason=analyzer_unavailable destination=%s:%u", address, port);
        goto done;
    }
    char request[256];
    int n = snprintf(request, sizeof(request),
        "CONNECT %s:%u HTTP/1.1\r\nHost: %s:%u\r\n\r\n",
        address, port, address, port);
    if (n <= 0 || (size_t)n >= sizeof(request) ||
        write_all(upstream, request, (size_t)n) != 0 ||
        accept_connect_response(upstream) != 0) {
        route_log("CONNECTION_ERROR reason=analyzer_connect destination=%s:%u", address, port);
        goto done;
    }
    route_log("CONNECTION_ROUTED destination=%s:%u", address, port);
    copy_both_ways(client, upstream);
done:
    if (upstream >= 0) close(upstream);
    close(client);
    __sync_sub_and_fetch(&workers, 1);
    return NULL;
}

static int parse_port(const char *value) {
    char *end = NULL;
    long number = strtol(value, &end, 10);
    if (!value[0] || (end && *end) || number < 1 || number > 65535) return -1;
    return (int)number;
}

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    int listen_port = parse_port(argv[1]);
    upstream_port = parse_port(argv[2]);
    if (listen_port < 0 || upstream_port < 0) return 2;
    log_fd = open(argv[3], O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    if (log_fd < 0) return 2;

    signal(SIGTERM, stop_requested);
    signal(SIGINT, stop_requested);
    signal(SIGPIPE, SIG_IGN);
    server_fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (server_fd < 0) return 3;
    int reuse = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    struct sockaddr_in local = {0};
    local.sin_family = AF_INET;
    local.sin_port = htons((uint16_t)listen_port);
    local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(server_fd, (struct sockaddr *)&local, sizeof(local)) < 0 ||
        listen(server_fd, ROUTE_BACKLOG) < 0) {
        route_log("START_ERROR errno=%d", errno);
        return 3;
    }
    route_log("ROUTE_READY port=%d analyzer_port=%d", listen_port, upstream_port);
    while (running) {
        int accepted = accept4(server_fd, NULL, NULL, SOCK_CLOEXEC);
        if (accepted < 0) {
            if (errno == EINTR) continue;
            if (!running) break;
            continue;
        }
        if (__sync_add_and_fetch(&workers, 1) > ROUTE_MAX_WORKERS) {
            __sync_sub_and_fetch(&workers, 1);
            close(accepted);
            route_log("CONNECTION_ERROR reason=capacity");
            continue;
        }
        pthread_t task;
        int rc = pthread_create(&task, NULL, handle_connection,
                                (void *)(intptr_t)accepted);
        if (rc == 0) pthread_detach(task);
        else {
            __sync_sub_and_fetch(&workers, 1);
            close(accepted);
            route_log("CONNECTION_ERROR reason=thread errno=%d", rc);
        }
    }
    route_log("ROUTE_STOP");
    close(log_fd);
    return 0;
}
