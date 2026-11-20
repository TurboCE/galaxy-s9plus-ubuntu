/* SPDX-License-Identifier: GPL-2.0-only */
#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <linux/gpio.h>
#include <poll.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    bool observe = true;
    const char *bank = "gpa3";
    unsigned offset = 6;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--initial-only"))
            observe = false;
        else if (!strcmp(argv[i], "--certify")) {
            bank = "gpa0";
            offset = 2;
        } else {
            return 8;
        }
    }
    glob_t devices;
    if (glob("/dev/gpiochip*", 0, NULL, &devices))
        return 1;
    int chip = -1;
    for (size_t i = 0; i < devices.gl_pathc; ++i) {
        int fd = open(devices.gl_pathv[i], O_RDONLY | O_CLOEXEC);
        if (fd < 0)
            continue;
        struct gpiochip_info info = {0};
        if (!ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, &info) && !strcmp(info.label, bank) &&
            info.lines == 8) {
            if (chip >= 0) {
                close(fd);
                close(chip);
                globfree(&devices);
                return 2;
            }
            chip = fd;
        } else {
            close(fd);
        }
    }
    globfree(&devices);
    if (chip < 0)
        return 3;

    struct gpio_v2_line_request request = {
        .offsets = {offset},
        .consumer = "g965n-hall-read-only",
        .config = {.flags = GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_EDGE_RISING |
                            GPIO_V2_LINE_FLAG_EDGE_FALLING},
        .num_lines = 1
    };
    if (ioctl(chip, GPIO_V2_GET_LINE_IOCTL, &request)) {
        perror("Could not claim the Hall input in read-only mode");
        close(chip);
        return 4;
    }
    close(chip);
    struct gpio_v2_line_values value = {.mask = 1};
    if (ioctl(request.fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &value)) {
        perror("Hall input read failed");
        close(request.fd);
        return 5;
    }
    bool state = !!(value.bits & 1);
    printf("Initial GPIO %s-%u state: %d\n", bank, offset, state);
    fflush(stdout);

    if (!observe) {
        close(request.fd);
        return 0;
    }

    struct pollfd watch = {.fd = request.fd, .events = POLLIN};
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    const time_t deadline = now.tv_sec + 110;
    for (;;) {
        clock_gettime(CLOCK_MONOTONIC, &now);
        if (now.tv_sec >= deadline)
            break;
        int status = poll(&watch, 1, 250);
        if (status < 0 && errno == EINTR)
            continue;
        if (status < 0 || (watch.revents & (POLLERR | POLLHUP | POLLNVAL)))
            return 6;
        if (status) {
            struct gpio_v2_line_event event;
            if (read(request.fd, &event, sizeof(event)) != sizeof(event))
                return 7;
            printf("Hall input edge: %s\n", event.id == GPIO_V2_LINE_EVENT_RISING_EDGE ?
                                             "rising" : "falling");
            fflush(stdout);
        }
        if (ioctl(request.fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &value))
            return 9;
        bool current = !!(value.bits & 1);
        if (current != state) {
            printf("Hall input level: %d\n", current);
            fflush(stdout);
            state = current;
        }
    }
    close(request.fd);
    return 0;
}
