/* SPDX-License-Identifier: GPL-2.0-only */
#include "g965n-wwan-client.h"

#include <string.h>

static const char * const requests[] = {
    [G965N_WWAN_REGISTRATION] = "registration",
    [G965N_WWAN_PACKET_ATTACHMENT] = "packet-attachment",
    [G965N_WWAN_SIGNAL_QUALITY] = "signal-quality",
    [G965N_WWAN_SIM_READINESS] = "sim-readiness",
    [G965N_WWAN_RADIO_STATE] = "radio-state",
    [G965N_WWAN_BEARER_STATUS] = "bearer-status",
    [G965N_WWAN_CONNECT_IPV4] = "connect-ipv4",
    [G965N_WWAN_DISCONNECT_IPV4] = "disconnect-ipv4",
    [G965N_WWAN_CELL_LIST] = "cell-list-request",
    [G965N_WWAN_CELL_INFO] = "cell-info",
};

static JsonObject *
wwan_request (const char *invocation,
              const char *command,
                    GCancellable *cancellable,
                    GError **error)
{
    g_autofree char *path = NULL;
    g_autoptr(GSocketAddress) address = NULL;
    g_autoptr(GSocket) socket = NULL;
    g_autoptr(GCredentials) credentials = NULL;
    g_autoptr(JsonParser) parser = NULL;
    JsonNode *root;
    gsize length;
    gssize transferred;
    char reply[32768];
    uid_t uid;

    if (!invocation || strlen (invocation) != 32 ||
        strspn (invocation, "0123456789abcdef") != 32 || !command) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                             "Invalid modem invocation or WWAN request");
        return NULL;
    }

    path = g_strdup_printf ("/run/g965n-wwan-%s.sock", invocation);
    address = g_unix_socket_address_new (path);
    socket = g_socket_new (G_SOCKET_FAMILY_UNIX, G_SOCKET_TYPE_SEQPACKET,
                           G_SOCKET_PROTOCOL_DEFAULT, error);
    if (!socket)
        return NULL;
    g_socket_set_timeout (socket, 4);

    if (!g_socket_connect (socket, address, cancellable, error))
        return NULL;
    credentials = g_socket_get_credentials (socket, error);
    if (!credentials)
        return NULL;
    uid = g_credentials_get_unix_user (credentials, error);
    if (uid == (uid_t) -1)
        return NULL;
    if (uid != 0) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_PERMISSION_DENIED,
                             "WWAN socket peer must be root");
        return NULL;
    }

    length = strlen (command);
    transferred = g_socket_send (socket, command, length, cancellable, error);
    if (transferred < 0)
        return NULL;
    if ((gsize) transferred != length) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_PARTIAL_INPUT,
                             "Short WWAN request");
        return NULL;
    }
    transferred = g_socket_receive (socket, reply, sizeof (reply), cancellable,
                                    error);
    if (transferred < 0)
        return NULL;
    if (!transferred || (gsize) transferred >= sizeof (reply) ||
        memchr (reply, '\0', transferred)) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_INVALID_DATA,
                             "Invalid WWAN response size or encoding");
        return NULL;
    }

    parser = json_parser_new ();
    if (!json_parser_load_from_data (parser, reply, transferred, error))
        return NULL;
    root = json_parser_get_root (parser);
    if (!root || !JSON_NODE_HOLDS_OBJECT (root)) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_INVALID_DATA,
                             "Expected a WWAN response object");
        return NULL;
    }
    return json_object_ref (json_node_get_object (root));
}

JsonObject *
g965n_wwan_request (const char *invocation, G965nWwanRequest request,
                    GCancellable *cancellable, GError **error)
{
    return wwan_request (invocation,
                         (guint) request < G_N_ELEMENTS (requests) ? requests[request] : NULL,
                         cancellable, error);
}

JsonObject *
g965n_wwan_connect_profile (const char *invocation, const char *apn,
                            GCancellable *cancellable, GError **error)
{
    g_autofree char *command = NULL;

    if (!apn || !apn[0] || strlen (apn) > 100 ||
        strspn (apn, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-") != strlen (apn)) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                             "A supported explicit APN is required");
        return NULL;
    }
    command = g_strdup_printf ("connect-ipv4:%s", apn);
    return wwan_request (invocation, command, cancellable, error);
}

JsonObject *
g965n_wwan_abort_generation (const char *invocation, guint generation, GError **error)
{
    g_autofree char *command = NULL;

    if (!generation || generation > 999999999) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                             "Invalid data generation");
        return NULL;
    }
    command = g_strdup_printf ("abort-ipv4:%u", generation);
    return wwan_request (invocation, command, NULL, error);
}

char *
g965n_wwan_get_invocation (GDBusConnection *system_bus,
                           GCancellable *cancellable,
                           GError **error)
{
    static const char service[] = "org.freedesktop.systemd1";
    static const char unit[] = "g965n-ril-lab-test.service";
    g_autoptr(GVariant) unit_reply = NULL;
    g_autoptr(GVariant) invocation_reply = NULL;
    g_autoptr(GVariant) invocation = NULL;
    const char *object_path;
    const guint8 *bytes;
    gsize length, i;
    g_autoptr(GString) hex = NULL;
    guint8 bits = 0;

    unit_reply = g_dbus_connection_call_sync (
        system_bus, service, "/org/freedesktop/systemd1",
        "org.freedesktop.systemd1.Manager", "GetUnit", g_variant_new ("(s)", unit),
        G_VARIANT_TYPE ("(o)"), G_DBUS_CALL_FLAGS_NONE, 2000, cancellable, error);
    if (!unit_reply)
        return NULL;
    g_variant_get (unit_reply, "(&o)", &object_path);

    invocation_reply = g_dbus_connection_call_sync (
        system_bus, service, object_path, "org.freedesktop.DBus.Properties", "Get",
        g_variant_new ("(ss)", "org.freedesktop.systemd1.Unit", "InvocationID"),
        G_VARIANT_TYPE ("(v)"), G_DBUS_CALL_FLAGS_NONE, 2000, cancellable, error);
    if (!invocation_reply)
        return NULL;
    g_variant_get (invocation_reply, "(v)", &invocation);
    if (g_variant_is_of_type (invocation, G_VARIANT_TYPE_BYTESTRING)) {
        bytes = g_variant_get_fixed_array (invocation, &length, sizeof (guint8));
        if (length == 16) {
            hex = g_string_sized_new (32);
            for (i = 0; i < length; i++) {
                bits |= bytes[i];
                g_string_append_printf (hex, "%02x", (guint) bytes[i]);
            }
        }
    }
    if (!bits) {
        g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_NOT_CONNECTED,
                             "The G965N RIL has no active invocation");
        return NULL;
    }
    return g_string_free (g_steal_pointer (&hex), FALSE);
}
