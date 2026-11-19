/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G965N_WWAN_CLIENT_H
#define G965N_WWAN_CLIENT_H

#include <gio/gio.h>
#include <json-glib/json-glib.h>

typedef enum {
    G965N_WWAN_REGISTRATION,
    G965N_WWAN_PACKET_ATTACHMENT,
    G965N_WWAN_SIGNAL_QUALITY,
    G965N_WWAN_SIM_READINESS,
    G965N_WWAN_RADIO_STATE,
    G965N_WWAN_BEARER_STATUS,
    G965N_WWAN_CONNECT_IPV4,
    G965N_WWAN_DISCONNECT_IPV4,
} G965nWwanRequest;

/* Call from a worker thread. A successful exchange returns a new object,
 * including a broker-declared error if the modem refused the request. */
JsonObject *g965n_wwan_request (const char *invocation,
                               G965nWwanRequest request,
                               GCancellable *cancellable,
                               GError **error);

/* Return the current systemd invocation for the bounded RIL test owner. */
char *g965n_wwan_get_invocation (GDBusConnection *system_bus,
                                GCancellable *cancellable,
                                GError **error);
JsonObject *g965n_wwan_connect_profile (const char *invocation, const char *apn,
                                       GCancellable *cancellable, GError **error);
JsonObject *g965n_wwan_abort_generation (const char *invocation, guint generation,
                                        GError **error);
#endif
