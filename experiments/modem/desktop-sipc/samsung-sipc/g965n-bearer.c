/* SPDX-License-Identifier: GPL-2.0-only */
#include "g965n-bearer.h"
#include "g965n-wwan-client.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct {
    MMBaseBearer parent;
    MMPort *data_port;
    char *invocation;
    guint generation;
} G965nBearer;

typedef struct { MMBaseBearerClass parent; } G965nBearerClass;

typedef struct {
    char *invocation;
    guint generation;
} DataSession;

static GType g965n_bearer_get_type (void);
G_DEFINE_TYPE (G965nBearer, g965n_bearer, MM_TYPE_BASE_BEARER)

static void
data_session_free (DataSession *session)
{
    g_free (session->invocation);
    g_free (session);
}

static JsonNode *
typed_member (JsonObject *record, const char *name, GType type)
{
    JsonNode *node = json_object_get_member (record, name);

    return node && json_node_get_value_type (node) == type ? node : NULL;
}

static guint
response_generation (JsonObject *record)
{
    JsonNode *node = typed_member (record, "generation", G_TYPE_INT64);
    gint64 value = node ? json_node_get_int (node) : 0;

    return value > 0 && value <= 999999999 ? (guint) value : 0;
}

static gboolean
valid_ipv4 (const char *text)
{
    struct in_addr address;
    guint32 value;

    if (!text || inet_pton (AF_INET, text, &address) != 1)
        return FALSE;
    value = ntohl (address.s_addr);
    return value && value != G_MAXUINT32 && (value >> 24) != 127 &&
           (value >> 16) != 0xa9fe && (value >> 28) != 0xe;
}

static MMBearerIpConfig *
read_ipv4_config (const char *invocation, guint generation, GError **error)
{
    g_autofree char *path = g_strdup_printf ("/run/g965n-lte-%s.json", invocation);
    g_autoptr(JsonParser) parser = json_parser_new ();
    char bytes[4097];
    struct stat st;
    gint fd;
    gssize count;
    JsonNode *node;
    JsonObject *root, *config;
    JsonArray *servers;
    const char *address, *gateway = NULL, *dns[3] = { NULL };
    gint64 mtu, prefix = 32;
    gdouble expiry, now;
    guint i;
    MMBearerIpConfig *ipv4;

    fd = open (path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        int saved_errno = errno;

        g_set_error (error, G_IO_ERROR, g_io_error_from_errno (saved_errno),
                     "Cannot open qualified LTE lease: %s", g_strerror (saved_errno));
        return NULL;
    }
    if (fstat (fd, &st) || !S_ISREG (st.st_mode) || st.st_uid != 0 ||
        st.st_nlink != 1 || (st.st_mode & 077) || st.st_size <= 0 ||
        st.st_size >= (off_t) sizeof (bytes)) {
        close (fd);
        goto invalid;
    }
    count = read (fd, bytes, sizeof (bytes));
    close (fd);
    if (count != st.st_size)
        goto invalid;
    if (!json_parser_load_from_data (parser, bytes, count, error))
        return NULL;
    node = json_parser_get_root (parser);
    if (!node || !JSON_NODE_HOLDS_OBJECT (node))
        goto invalid;
    root = json_node_get_object (node);
    now = (gdouble) g_get_monotonic_time () / G_TIME_SPAN_SECOND;
    node = json_object_get_member (root, "valid_until");
    if (!node || (json_node_get_value_type (node) != G_TYPE_DOUBLE &&
                  json_node_get_value_type (node) != G_TYPE_INT64))
        goto invalid;
    expiry = json_node_get_double (node);
    if (!isfinite (expiry) || expiry <= now || expiry > now + 6 ||
        response_generation (root) != generation)
        goto invalid;
    node = json_object_get_member (root, "config");
    if (!node || !JSON_NODE_HOLDS_OBJECT (node))
        goto invalid;
    config = json_node_get_object (node);
    node = typed_member (config, "cid", G_TYPE_INT64);
    if (!node || json_node_get_int (node) != 1)
        goto invalid;
    node = typed_member (config, "ipv4", G_TYPE_STRING);
    address = node ? json_node_get_string (node) : NULL;
    if (!valid_ipv4 (address))
        goto invalid;
    node = typed_member (config, "mtu", G_TYPE_INT64);
    mtu = node ? json_node_get_int (node) : 0;
    if (mtu < 576 || mtu > 1500)
        goto invalid;
    node = json_object_get_member (config, "prefix4");
    if (node && !JSON_NODE_HOLDS_NULL (node)) {
        if (json_node_get_value_type (node) != G_TYPE_INT64)
            goto invalid;
        prefix = json_node_get_int (node);
        if (prefix < 1 || prefix > 32)
            goto invalid;
    }
    node = json_object_get_member (config, "gateway");
    if (node && !JSON_NODE_HOLDS_NULL (node)) {
        if (json_node_get_value_type (node) != G_TYPE_STRING)
            goto invalid;
        gateway = json_node_get_string (node);
        if (!valid_ipv4 (gateway))
            goto invalid;
    }
    node = json_object_get_member (config, "dns4");
    if (!node || !JSON_NODE_HOLDS_ARRAY (node))
        goto invalid;
    servers = json_node_get_array (node);
    if (json_array_get_length (servers) < 1 || json_array_get_length (servers) > 2)
        goto invalid;
    for (i = 0; i < json_array_get_length (servers); i++) {
        node = json_array_get_element (servers, i);
        if (json_node_get_value_type (node) != G_TYPE_STRING)
            goto invalid;
        dns[i] = json_node_get_string (node);
        if (!valid_ipv4 (dns[i]))
            goto invalid;
    }

    ipv4 = mm_bearer_ip_config_new ();
    mm_bearer_ip_config_set_method (ipv4, MM_BEARER_IP_METHOD_STATIC);
    mm_bearer_ip_config_set_address (ipv4, address);
    mm_bearer_ip_config_set_prefix (ipv4, prefix);
    mm_bearer_ip_config_set_gateway (ipv4, gateway);
    mm_bearer_ip_config_set_dns (ipv4, dns);
    mm_bearer_ip_config_set_mtu (ipv4, mtu);
    return ipv4;

invalid:
    g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_FAILED,
                         "Malformed, stale or mismatched LTE IPv4 lease");
    return NULL;
}

static gboolean
wait_state (const DataSession *session, const char *target, gint64 seconds,
            GCancellable *cancellable, GError **error)
{
    gint64 deadline = g_get_monotonic_time () + seconds * G_TIME_SPAN_SECOND;

    while (g_get_monotonic_time () < deadline) {
        g_autoptr(JsonObject) response = NULL;
        JsonNode *state;
        const char *name;

        response = g965n_wwan_request (session->invocation, G965N_WWAN_BEARER_STATUS,
                                       cancellable, error);
        if (!response)
            return FALSE;
        state = typed_member (response, "state", G_TYPE_STRING);
        name = state ? json_node_get_string (state) : NULL;
        if (!name || response_generation (response) != session->generation ||
            g_str_equal (name, "failed")) {
            g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_FAILED,
                                 "SIPC data session changed or failed");
            return FALSE;
        }
        if (g_str_equal (name, target))
            return TRUE;
        if (g_cancellable_set_error_if_cancelled (cancellable, error))
            return FALSE;
        g_usleep (250000);
    }
    g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_TIMEOUT,
                         "Timed out waiting for a SIPC data state");
    return FALSE;
}

static void
connect_thread (GTask *task, gpointer source, gpointer task_data,
                GCancellable *cancellable)
{
    G965nBearer *self = source;
    DataSession *session = task_data;
    g_autoptr(GDBusConnection) bus = NULL;
    g_autoptr(JsonObject) response = NULL;
    g_autoptr(MMBearerIpConfig) ipv4 = NULL;
    g_autoptr(GError) error = NULL;
    JsonNode *accepted;
    const char *apn = mm_bearer_properties_get_apn (mm_base_bearer_peek_config (MM_BASE_BEARER (self)));

    bus = g_bus_get_sync (G_BUS_TYPE_SYSTEM, cancellable, &error);
    if (!bus)
        goto failed;
    session->invocation = g965n_wwan_get_invocation (bus, cancellable, &error);
    if (!session->invocation || g_cancellable_set_error_if_cancelled (cancellable, &error))
        goto failed;
    /* Once sent, collect the acceptance even if the caller cancels. */
    response = g965n_wwan_connect_profile (session->invocation, apn, NULL, &error);
    if (!response)
        goto failed;
    accepted = typed_member (response, "accepted", G_TYPE_BOOLEAN);
    if (!accepted || !json_node_get_boolean (accepted) ||
        !(session->generation = response_generation (response))) {
        g_set_error_literal (&error, MM_CORE_ERROR, MM_CORE_ERROR_FAILED,
                             "SIPC rejected the data profile or the modem already has a data owner");
        goto failed;
    }
    if (!wait_state (session, "connected", 35, cancellable, &error))
        goto failed;
    ipv4 = read_ipv4_config (session->invocation, session->generation, &error);
    if (!ipv4 || g_cancellable_set_error_if_cancelled (cancellable, &error))
        goto failed;
    g_task_return_pointer (task, mm_bearer_connect_result_new (self->data_port, ipv4, NULL),
                           (GDestroyNotify) mm_bearer_connect_result_unref);
    return;

failed:
    if (session->generation) {
        g_autoptr(JsonObject) abort_reply = g965n_wwan_abort_generation (session->invocation,
                                                                        session->generation, NULL);
        (void) abort_reply;
    }
    g_task_return_error (task, g_steal_pointer (&error));
}

static void
bearer_connect (MMBaseBearer *bearer, GCancellable *cancellable,
                GAsyncReadyCallback callback, gpointer user_data)
{
    g_autoptr(GTask) task = g_task_new (bearer, cancellable, callback, user_data);

    g_task_set_check_cancellable (task, FALSE);
    g_task_set_task_data (task, g_new0 (DataSession, 1), (GDestroyNotify) data_session_free);
    g_task_run_in_thread (task, connect_thread);
}

static MMBearerConnectResult *
bearer_connect_finish (MMBaseBearer *bearer, GAsyncResult *result, GError **error)
{
    G965nBearer *self = (G965nBearer *) bearer;
    MMBearerConnectResult *connected;
    DataSession *session;

    g_assert (g_task_is_valid (result, bearer));
    connected = g_task_propagate_pointer (G_TASK (result), error);
    if (connected) {
        session = g_task_get_task_data (G_TASK (result));
        g_free (self->invocation);
        self->invocation = g_steal_pointer (&session->invocation);
        self->generation = session->generation;
    }
    return connected;
}

static void
disconnect_thread (GTask *task, gpointer source, gpointer task_data,
                   GCancellable *cancellable)
{
    DataSession *session = task_data;
    g_autoptr(GError) error = NULL;
    g_autoptr(JsonObject) response = NULL;

    (void) source;
    (void) cancellable;
    if (!session->generation) {
        g_task_return_boolean (task, TRUE);
        return;
    }
    response = g965n_wwan_abort_generation (session->invocation, session->generation, &error);
    if (!response || !wait_state (session, "idle", 15, NULL, &error)) {
        g_task_return_error (task, g_steal_pointer (&error));
        return;
    }
    g_task_return_boolean (task, TRUE);
}

static void
bearer_disconnect (MMBaseBearer *bearer, GAsyncReadyCallback callback, gpointer user_data)
{
    G965nBearer *self = (G965nBearer *) bearer;
    g_autoptr(GTask) task = g_task_new (bearer, NULL, callback, user_data);
    DataSession *session = g_new0 (DataSession, 1);

    session->invocation = g_strdup (self->invocation);
    session->generation = self->generation;
    g_task_set_task_data (task, session, (GDestroyNotify) data_session_free);
    g_task_run_in_thread (task, disconnect_thread);
}

static gboolean
bearer_disconnect_finish (MMBaseBearer *bearer, GAsyncResult *result, GError **error)
{
    G965nBearer *self = (G965nBearer *) bearer;

    g_assert (g_task_is_valid (result, bearer));
    if (!g_task_propagate_boolean (G_TASK (result), error))
        return FALSE;
    g_clear_pointer (&self->invocation, g_free);
    self->generation = 0;
    return TRUE;
}

static void
status_thread (GTask *task, gpointer source, gpointer task_data, GCancellable *cancellable)
{
    DataSession *session = task_data;
    g_autoptr(GError) error = NULL;
    g_autoptr(JsonObject) response = NULL;
    JsonNode *state;
    MMBearerConnectionStatus status = MM_BEARER_CONNECTION_STATUS_DISCONNECTED;

    (void) source;
    if (session->generation) {
        response = g965n_wwan_request (session->invocation, G965N_WWAN_BEARER_STATUS,
                                       cancellable, &error);
        if (!response && !g_error_matches (error, G_IO_ERROR, G_IO_ERROR_NOT_FOUND) &&
            !g_error_matches (error, G_IO_ERROR, G_IO_ERROR_CONNECTION_REFUSED)) {
            g_task_return_error (task, g_steal_pointer (&error));
            return;
        }
    }
    if (response) {
        state = typed_member (response, "state", G_TYPE_STRING);
        if (!state) {
            g_task_return_new_error (task, MM_CORE_ERROR, MM_CORE_ERROR_RETRY,
                                     "SIPC bearer status is temporarily unavailable");
            return;
        }
        if (response_generation (response) == session->generation &&
            g_str_equal (json_node_get_string (state), "connected"))
            status = MM_BEARER_CONNECTION_STATUS_CONNECTED;
    }
    g_task_return_int (task, status);
}

static void
load_connection_status (MMBaseBearer *bearer, GAsyncReadyCallback callback, gpointer user_data)
{
    G965nBearer *self = (G965nBearer *) bearer;
    g_autoptr(GTask) task = g_task_new (bearer, NULL, callback, user_data);
    DataSession *session = g_new0 (DataSession, 1);

    session->invocation = g_strdup (self->invocation);
    session->generation = self->generation;
    g_task_set_task_data (task, session, (GDestroyNotify) data_session_free);
    g_task_run_in_thread (task, status_thread);
}

static MMBearerConnectionStatus
load_connection_status_finish (MMBaseBearer *bearer, GAsyncResult *result, GError **error)
{
    gssize status;

    g_assert (g_task_is_valid (result, bearer));
    status = g_task_propagate_int (G_TASK (result), error);
    return status < 0 ? MM_BEARER_CONNECTION_STATUS_UNKNOWN : (MMBearerConnectionStatus) status;
}

static void
g965n_bearer_init (G965nBearer *self)
{
    (void) self;
}

static void
g965n_bearer_finalize (GObject *object)
{
    G965nBearer *self = (G965nBearer *) object;

    g_clear_object (&self->data_port);
    g_free (self->invocation);
    G_OBJECT_CLASS (g965n_bearer_parent_class)->finalize (object);
}

static void
g965n_bearer_class_init (G965nBearerClass *klass)
{
    MMBaseBearerClass *bearer = MM_BASE_BEARER_CLASS (klass);
    G_OBJECT_CLASS (klass)->finalize = g965n_bearer_finalize;
    bearer->connect = bearer_connect;
    bearer->connect_finish = bearer_connect_finish;
    bearer->disconnect = bearer_disconnect;
    bearer->disconnect_finish = bearer_disconnect_finish;
    bearer->load_connection_status = load_connection_status;
    bearer->load_connection_status_finish = load_connection_status_finish;
}

MMBaseBearer *
g965n_bearer_new (MMBaseModem *modem, MMBearerProperties *properties, GError **error)
{
    g_autoptr(MMPort) port = NULL;
    G965nBearer *self;
    MMBearerIpFamily family = mm_bearer_properties_get_ip_type (properties);
    MMBearerAllowedAuth auth = mm_bearer_properties_get_allowed_auth (properties);
    const char *apn = mm_bearer_properties_get_apn (properties);

    if ((family != MM_BEARER_IP_FAMILY_NONE && family != MM_BEARER_IP_FAMILY_IPV4 &&
         family != MM_BEARER_IP_FAMILY_ANY) ||
        (auth != MM_BEARER_ALLOWED_AUTH_UNKNOWN && auth != MM_BEARER_ALLOWED_AUTH_NONE) ||
        mm_bearer_properties_get_user (properties) || mm_bearer_properties_get_password (properties) ||
        mm_bearer_properties_get_multiplex (properties) == MM_BEARER_MULTIPLEX_SUPPORT_REQUIRED ||
        mm_bearer_properties_get_profile_id (properties) > 0 ||
        !apn || !apn[0]) {
        g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_UNSUPPORTED,
                             "Expected an explicit IPv4 APN with no subscriber credentials or multiplexing");
        return NULL;
    }
    port = mm_base_modem_get_best_data_port (modem, MM_PORT_TYPE_NET);
    if (!port || g_strcmp0 (mm_port_get_device (port), "rmnet0")) {
        g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_NOT_FOUND,
                             "Expected the physical SIPC data port");
        return NULL;
    }
    self = g_object_new (g965n_bearer_get_type (), MM_BASE_BEARER_MODEM, modem,
                         MM_BASE_BEARER_CONFIG, properties, "ip-timeout", 35, NULL);
    self->data_port = g_steal_pointer (&port);
    mm_base_bearer_export (MM_BASE_BEARER (self));
    return MM_BASE_BEARER (self);
}
