/* SPDX-License-Identifier: GPL-2.0-only */
/* Diagnostic client for the legacy 64-bit Android GNSS HAL ABI. */
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
#include <pthread.h>
#include <poll.h>
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
extern int *__errno(void);
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
    /* Own-device Samsung extension following the 96-byte legacy prefix. */
    void (*request_location)(bool independent_from_gnss, bool user_emergency);
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
_Static_assert(offsetof(struct callbacks, request_location) == 96,
               "SM-G965N callback extension requires the LP64 legacy prefix");

static atomic_uint fixes, gps_sv, nmea_records, status_records, status_values[8];
static atomic_uint nmea_valid, nmea_forwarded;
static atomic_uint capability_mask;
static atomic_uint xtra_requests;
static atomic_uint visible_satellites_max;
static atomic_uint location_requests;
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
struct satellites_prefix {
    size_t size;
    int count;
};
static void satellites(void *value)
{
    const struct satellites_prefix *sample = value;
    if (!sample)
        return;
    ++gps_sv;
    if (sample->size >= sizeof(*sample) && sample->count >= 0 && sample->count <= 256) {
        unsigned previous = atomic_load(&visible_satellites_max);
        while ((unsigned)sample->count > previous &&
               !atomic_compare_exchange_weak(&visible_satellites_max, &previous,
                                             (unsigned)sample->count)) {}
    }
}
static void noop(void) {}
static void system_info(const void *value) { (void)value; }
static void capabilities(uint32_t flags) { atomic_store(&capability_mask, flags); }
static void request_location(bool independent_from_gnss, bool user_emergency)
{
    (void)independent_from_gnss;
    (void)user_emergency;
    /* Never reenter GeoClue or inject a GNSS fix from the callback thread. */
    ++location_requests;
}
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

struct xtra_callbacks {
    void (*download_request)(void);
    pthread_t (*thread)(const char *, void (*)(void *), void *);
};
struct xtra_interface {
    size_t size;
    int (*init)(struct xtra_callbacks *);
    int (*inject)(char *, int);
};
static void request_xtra(void) { ++xtra_requests; }

static void provide_xtra(const struct interface *gps)
{
    struct xtra_callbacks callbacks = {.download_request = request_xtra, .thread = spawn};
    const struct xtra_interface *xtra = gps->extension ? gps->extension("gps-xtra") : NULL;
    if (!xtra || xtra->size < sizeof(*xtra) || !xtra->init || !xtra->inject) {
        printf("GNSS XTRA interface unavailable\n");
        return;
    }
    /* Keep callbacks alive for HAL threads after this function returns. */
    static struct xtra_callbacks persistent;
    persistent = callbacks;
    int rc = xtra->init(&persistent);
    printf("GNSS XTRA init result: %d\n", rc);
    if (rc)
        return;
    off_t bytes = lseek(4, 0, SEEK_END);
    if (bytes <= 512 || bytes > 512 * 1024 || lseek(4, 0, SEEK_SET) != 0)
        return;
    char *data = malloc((size_t)bytes);
    if (!data)
        return;
    off_t received = 0;
    while (received < bytes) {
        ssize_t count = read(4, data + received, (size_t)(bytes - received));
        if (count < 0 && *__errno() == EINTR)
            continue;
        if (count <= 0)
            break;
        received += count;
    }
    if (received == bytes) {
        rc = xtra->inject(data, (int)bytes);
        printf("GNSS XTRA injection result: %d (bytes=%ld)\n", rc, (long)bytes);
    }
    free(data);
}

static int64_t milliseconds(const struct timespec *value)
{
    return (int64_t)value->tv_sec * 1000 + value->tv_nsec / 1000000;
}

static void provide_utc(const struct interface *gps)
{
    struct timespec before, utc, after;
    if (!gps->inject_time || clock_gettime(CLOCK_BOOTTIME, &before) ||
        clock_gettime(CLOCK_REALTIME, &utc) ||
        clock_gettime(CLOCK_BOOTTIME, &after))
        return;

    const int64_t first = milliseconds(&before);
    const int64_t span = milliseconds(&after) - first;
    if (span < 0 || span > 100 || utc.tv_sec < 1704067200)
        return;

    int rc = gps->inject_time(milliseconds(&utc), first + span / 2, 1000);
    printf("GNSS UTC injection result: %d\n", rc);
}

static void provide_seed(const struct interface *gps)
{
    char data[192], *cursor, *end;
    double values[4], lat, lon, accuracy, stamp;
    struct timespec now;
    if (lseek(5, 0, SEEK_SET) != 0) return;
    ssize_t n = read(5, data, sizeof(data)-1);
    if (n <= 0 || n == (ssize_t)sizeof(data)-1 || !gps->inject_location) return;
    if (memchr(data, 0, (size_t)n)) goto invalid;
    data[n] = 0;
    if (strncmp(data, "v1 ", 3)) goto invalid;
    cursor = data + 3;
    for (int i=0; i<4; i++) {
        values[i] = strtod(cursor, &end);
        if (end == cursor || (*end && *end != ' ' && *end != '\n' && *end != '\r' && *end != '\t')) goto invalid;
        cursor = end;
    }
    while (*cursor==' ' || *cursor=='\n' || *cursor=='\r' || *cursor=='\t') cursor++;
    if (*cursor) goto invalid;
    lat=values[0]; lon=values[1]; accuracy=values[2]; stamp=values[3];
    if (!__builtin_isfinite(lat) || !__builtin_isfinite(lon) ||
        !__builtin_isfinite(accuracy) || !__builtin_isfinite(stamp) ||
        lat < -90 || lat > 90 || lon < -180 || lon > 180 ||
        accuracy < 1 || accuracy > 100000 || clock_gettime(CLOCK_REALTIME, &now) ||
        stamp > now.tv_sec + now.tv_nsec/1e9 ||
        now.tv_sec + now.tv_nsec/1e9 - stamp > 300) {
        goto invalid;
    }
    accuracy += 350 * (now.tv_sec + now.tv_nsec/1e9 - stamp);
    if (accuracy > 100000) goto invalid;
    printf("GNSS position injection result: %d\n", gps->inject_location(lat, lon, (float)accuracy));
    return;
invalid:
    puts("GNSS position injection result: -22");
}

static void service_location_request(const struct interface *gps, bool enabled,
                                     bool independent_seed, unsigned *served)
{
    unsigned requests = atomic_load(&location_requests);
    if (!enabled || !independent_seed || requests == *served) return;
    provide_seed(gps);
    *served = requests;
    printf("GNSS requested network seed replay: %u\n", requests);
}


int main(int argc, char **argv, char **envp)
{
    const struct interface *(*get_gps)(void);
    const struct interface *gps;
    static struct callbacks cb = {
        .size = sizeof(cb), .location = location, .status = status,
        .satellites = satellites, .nmea = nmea, .capabilities = capabilities,
        .acquire = noop, .release = noop, .thread = spawn, .utc_time = noop,
        .system_info = system_info, .gnss_satellites = satellites,
        .request_location = request_location
    };
    int rc;
    unsigned long seconds = 24;
    bool inject_utc = false, inject_xtra = false, inject_seed = false, on_demand = false;
    bool seed_independent = false;
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--inject-current-utc") && !inject_utc)
            inject_utc = true;
        else if (!strcmp(argv[i], "--seed-fd5") && !inject_seed)
            inject_seed = true;
        else if (!strcmp(argv[i], "--seed-independent") && !seed_independent)
            seed_independent = true;
        else if (!strcmp(argv[i], "--xtra-fd4") && !inject_xtra)
            inject_xtra = true;
        else if (!strcmp(argv[i], "--serve-nmea-fd3") && !forward_nmea)
            forward_nmea = on_demand = true;
        else if (!strcmp(argv[i], "--nmea-fd3") && !forward_nmea)
            forward_nmea = true;
        else
            return 4;
    }
    if (seed_independent && !inject_seed) return 4;
    if (argc >= 2) {
        char *end;
        seconds = strtoul(argv[1], &end, 10);
        if (end == argv[1] || *end || seconds < 1 || seconds > 240)
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
    if (gps->extension) {
        static const char *const names[] = {
            "gps-xtra", "agps", "agps_ril", "gps-debug", "gnss_configuration"
        };
        for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
            printf("GNSS extension %s available: %d\n", names[i],
                   gps->extension(names[i]) != NULL);
    }
    rc = gps->set_mode(0, 0, 1000, 0, 0);
    printf("Standalone GNSS mode result: %d\n", rc);
    if (!rc) {
        rc = gps->start();
        printf("HAL start result: %d\n", rc);
        if (!rc) {
            int waited = 0;
            if (inject_utc)
                provide_utc(gps);
            if (inject_seed)
                provide_seed(gps);
            if (inject_xtra)
                provide_xtra(gps);
            if (on_demand) {
                struct pollfd control = {.fd = STDIN_FILENO, .events = POLLIN};
                int status;
                unsigned idle_seconds = 0;
                unsigned served_requests = 0;
                do {
                    status = poll(&control, 1, 1000);
                    if (!status)
                        service_location_request(gps, inject_seed, seed_independent, &served_requests);
                    if (!status && ++idle_seconds % 15 == 0) {
                        printf("GNSS live: satellite_callbacks=%u visible_max=%u fixes=%u nmea=%u\n",
                               atomic_load(&gps_sv), atomic_load(&visible_satellites_max),
                               atomic_load(&fixes), atomic_load(&nmea_valid));
                        printf("GNSS location assistance requests: %u\n", atomic_load(&location_requests));
                    }
                } while (status == 0 || (status < 0 && *__errno() == EINTR));
                if (status < 0)
                    waited = *__errno();
            } else {
                struct timespec limit;
                waited = clock_gettime(CLOCK_MONOTONIC, &limit);
                if (!waited) {
                    limit.tv_sec += seconds;
                    do {
                        waited = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &limit, NULL);
                    } while (waited == EINTR);
                }
            }
            printf("GNSS wait result: %d (requested %lu seconds)\n", waited, seconds);
            if (waited)
                rc = 5;
            printf("GNSS callbacks: status=%u satellites=%u nmea=%u location=%u\n",
                   atomic_load(&status_records), atomic_load(&gps_sv),
                   atomic_load(&nmea_records), atomic_load(&fixes));
            printf("GNSS checksum-valid NMEA: %u, forwarded: %u\n",
                   atomic_load(&nmea_valid), atomic_load(&nmea_forwarded));
            printf("GNSS capability mask: %u\n", atomic_load(&capability_mask));
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
