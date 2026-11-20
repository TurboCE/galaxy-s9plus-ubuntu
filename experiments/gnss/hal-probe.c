/* SPDX-License-Identifier: GPL-2.0-only */
/* Diagnostic client for the legacy 64-bit Android GNSS HAL ABI. */
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
#include <pthread.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef void (*array_function)(void);
struct constructor_arrays {
    array_function *preinit;
    array_function *init;
    array_function *fini;
};
extern void __libc_init(void *, void *, int (*)(int, char **, char **),
                        const struct constructor_arrays *) __attribute__((noreturn));
int main(int argc, char **argv, char **envp);
__attribute__((used)) static void start_main(void *sp)
{
    static array_function sentinel[] = {(array_function)-1, NULL};
    const struct constructor_arrays arrays = {sentinel, sentinel, sentinel};
    __libc_init(sp, NULL, main, &arrays);
}
__asm__(".text; .global _start; .type _start,%function; _start: mov x0,sp; b start_main");

struct callbacks {
    size_t size;
    void (*location)(void *);
    void (*status)(void *);
    void (*satellites)(void *);
    void (*nmea)(int64_t, const char *, int);
    void (*capabilities)(uint32_t);
    void (*acquire)(void);
    void (*release)(void);
    pthread_t (*thread)(const char *, void (*)(void *), void *);
    void (*utc_time)(void);
    void (*system_info)(const void *);
    void (*gnss_satellites)(void *);
};

struct interface {
    size_t size;
    int (*init)(struct callbacks *);
    int (*start)(void);
    int (*stop)(void);
    void (*cleanup)(void);
    int (*inject_time)(int64_t, int64_t, int);
    int (*inject_location)(double, double, float);
    void (*delete_aiding_data)(uint16_t);
    int (*set_mode)(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
    const void *(*extension)(const char *);
};

static atomic_uint fixes, gps_sv, nmea_records, status_records, status_values[8];
static atomic_uint nmea_valid, nmea_forwarded;
static bool forward_nmea;
struct status_value {
    size_t size;
    uint16_t status;
};
struct location_prefix {
    size_t size;
    uint16_t flags;
};
static void location(void *value)
{
    const struct location_prefix *sample = value;
    if (sample && sample->size >= sizeof(*sample) && (sample->flags & 1))
        ++fixes;
}
static void status(void *value)
{
    const struct status_value *sample = value;
    if (sample && sample->size >= sizeof(*sample)) {
        ++status_records;
        if (sample->status < 8)
            ++status_values[sample->status];
    }
}
static void satellites(void *value) { if (value) ++gps_sv; }
static void noop(void) {}
static void system_info(const void *value) { (void)value; }
static void capabilities(uint32_t flags) { (void)flags; }
static int hex_value(unsigned char byte)
{
    if (byte >= '0' && byte <= '9')
        return byte - '0';
    if (byte >= 'A' && byte <= 'F')
        return byte - 'A' + 10;
    if (byte >= 'a' && byte <= 'f')
        return byte - 'a' + 10;
    return -1;
}

static void nmea(int64_t time, const char *sentence, int len)
{
    char frame[258];
    unsigned checksum = 0;
    (void)time;
    if (!sentence || len < 8 || len > 256 || sentence[0] != '$')
        return;
    ++nmea_records;
    while (len > 0 && (sentence[len - 1] == '\0' ||
                       sentence[len - 1] == '\r' || sentence[len - 1] == '\n'))
        --len;
    if (len < 8 || sentence[len - 3] != '*')
        return;
    for (int i = 1; i < len - 3; i++) {
        unsigned char byte = sentence[i];
        if (byte < 0x20 || byte > 0x7e || byte == '$' || byte == '*')
            return;
        checksum ^= byte;
    }
    int high = hex_value(sentence[len - 2]);
    int low = hex_value(sentence[len - 1]);
    if (high < 0 || low < 0 || checksum != (unsigned)(high * 16 + low))
        return;
    ++nmea_valid;
    if (forward_nmea) {
        memcpy(frame, sentence, len);
        frame[len] = '\r';
        frame[len + 1] = '\n';
        if (write(3, frame, len + 2) == len + 2)
            ++nmea_forwarded;
    }
}

struct task {
    void (*start)(void *);
    void *context;
};
static void *thread_entry(void *raw)
{
    struct task task = *(struct task *)raw;
    free(raw);
    task.start(task.context);
    return NULL;
}
static pthread_t spawn(const char *name, void (*start)(void *), void *context)
{
    pthread_t id;
    struct task *task = malloc(sizeof(*task));
    (void)name;
    if (!task)
        return 0;
    *task = (struct task){start, context};
    if (pthread_create(&id, NULL, thread_entry, task)) {
        free(task);
        return 0;
    }
    return id;
}

int main(int argc, char **argv, char **envp)
{
    const struct interface *(*get_gps)(void);
    const struct interface *gps;
    struct callbacks cb = {
        .size = sizeof(cb), .location = location, .status = status,
        .satellites = satellites, .nmea = nmea, .capabilities = capabilities,
        .acquire = noop, .release = noop, .thread = spawn, .utc_time = noop,
        .system_info = system_info, .gnss_satellites = satellites
    };
    int rc;
    unsigned long seconds = 24;
    if (argc > 3 || (argc == 3 && strcmp(argv[2], "--nmea-fd3")))
        return 4;
    forward_nmea = argc == 3;
    if (argc >= 2) {
        char *end;
        seconds = strtoul(argv[1], &end, 10);
        if (end == argv[1] || *end || seconds < 1 || seconds > 120)
            return 4;
    }
    (void)envp;
    setvbuf(stdout, NULL, _IOLBF, 0);
    void *handle = dlopen("/vendor/lib64/hw/gps.default.so", RTLD_NOW);
    if (!handle) {
        printf("GNSS HAL dynamic loading failed: %s\n", dlerror());
        return 1;
    }
    get_gps = dlsym(handle, "gps_get_hardware_interface");
    if (!get_gps || !(gps = get_gps()) || gps->size < sizeof(*gps) ||
        !gps->init || !gps->set_mode || !gps->start || !gps->stop || !gps->cleanup) {
        printf("Unexpected GNSS HAL interface\n");
        return 2;
    }
    printf("HAL interface bytes: %zu\n", gps->size);
    rc = gps->init(&cb);
    printf("HAL init result: %d\n", rc);
    if (rc)
        return 3;
    rc = gps->set_mode(0, 0, 1000, 0, 0);
    printf("Standalone GNSS mode result: %d\n", rc);
    if (!rc) {
        rc = gps->start();
        printf("HAL start result: %d\n", rc);
        if (!rc) {
            struct timespec limit;
            int waited = clock_gettime(CLOCK_MONOTONIC, &limit);
            if (!waited) {
                limit.tv_sec += seconds;
                do {
                    waited = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &limit, NULL);
                } while (waited == EINTR);
            }
            printf("GNSS wait result: %d (requested %lu seconds)\n", waited, seconds);
            if (waited)
                rc = 5;
            printf("GNSS callbacks: status=%u satellites=%u nmea=%u location=%u\n",
                   atomic_load(&status_records), atomic_load(&gps_sv),
                   atomic_load(&nmea_records), atomic_load(&fixes));
            printf("GNSS checksum-valid NMEA: %u, forwarded: %u\n",
                   atomic_load(&nmea_valid), atomic_load(&nmea_forwarded));
            for (unsigned i = 0; i < 8; i++) {
                unsigned count = atomic_load(&status_values[i]);
                if (count)
                    printf("GNSS status code %u occurred %u times\n", i, count);
            }
            gps->stop();
        }
    }
    gps->cleanup();
    return rc != 0;
}
