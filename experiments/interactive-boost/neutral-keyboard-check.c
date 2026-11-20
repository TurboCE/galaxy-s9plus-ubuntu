// SPDX-License-Identifier: GPL-2.0-only
/* Bounded validation input: advertise a keyboard, emit only Shift press/release.
 * Caller must perform the model/BOOT/backup checks and own any temporary uinput
 * module lifecycle. No text, pointer events, persistent devices or input reads.
 */
#include <fcntl.h>
#include <linux/uinput.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static int event(int fd, unsigned short type, unsigned short code, int value)
{
	struct input_event e = { .type = type, .code = code, .value = value };
	return write(fd, &e, sizeof(e)) != (ssize_t)sizeof(e);
}

int main(void)
{
	struct uinput_setup setup = { .id = { .bustype = BUS_VIRTUAL } };
	struct pollfd input = { .fd = STDIN_FILENO, .events = POLLIN };
	const struct timespec settle = { .tv_nsec = 300000000 };
	const struct timespec finish = { .tv_sec = 1 };
	int fd, result = 1;
	char command;
	/* Termination also closes the fd, letting uinput destroy its own device. */
	alarm(10);
	fd = open("/dev/uinput", O_WRONLY | O_CLOEXEC);
	if (fd < 0)
		return 2;
	strcpy(setup.name, "G965N bounded input QoS validation");
	if (ioctl(fd, UI_SET_EVBIT, EV_KEY) ||
	    ioctl(fd, UI_SET_KEYBIT, KEY_A) ||
	    ioctl(fd, UI_SET_KEYBIT, KEY_LEFTMETA) ||
	    ioctl(fd, UI_SET_KEYBIT, KEY_LEFTSHIFT) ||
	    ioctl(fd, UI_DEV_SETUP, &setup) || ioctl(fd, UI_DEV_CREATE))
		goto close;
	nanosleep(&settle, NULL);
	puts("READY");
	fflush(stdout);
	if (poll(&input, 1, 5000) != 1 || read(STDIN_FILENO, &command, 1) != 1 ||
	    command != '1')
		goto destroy;
	if (event(fd, EV_KEY, KEY_LEFTSHIFT, 1) ||
	    event(fd, EV_SYN, SYN_REPORT, 0) ||
	    event(fd, EV_KEY, KEY_LEFTSHIFT, 0) ||
	    event(fd, EV_SYN, SYN_REPORT, 0))
		goto destroy;
	puts("SENT");
	fflush(stdout);
	nanosleep(&finish, NULL);
	result = 0;
destroy:
	if (ioctl(fd, UI_DEV_DESTROY))
		result = 3;
close:
	close(fd);
	return result;
}
