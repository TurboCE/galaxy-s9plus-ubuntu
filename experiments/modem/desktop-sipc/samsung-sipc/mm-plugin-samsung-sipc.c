/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "mm-plugin-common.h"
#include "mm-broadband-modem.h"
#include "mm-iface-modem.h"
#include "mm-iface-modem-3gpp.h"
#include "mm-iface-modem-location.h"

#include "g965n-wwan-client.h"
#include "g965n-bearer.h"

typedef struct { MMBroadbandModem parent; guint location_poll; gboolean location_pending; } G965nModem;
typedef struct { MMBroadbandModemClass parent; } G965nModemClass;

GType g965n_modem_get_type (void);
static void modem_iface_init (MMIfaceModem *iface);
static void location_iface_init (MMIfaceModemLocation *iface);
static void modem_3gpp_iface_init (MMIfaceModem3gpp *iface);
G_DEFINE_TYPE_EXTENDED (G965nModem, g965n_modem, MM_TYPE_BROADBAND_MODEM, 0,
                        G_IMPLEMENT_INTERFACE (MM_TYPE_IFACE_MODEM, modem_iface_init)
                        G_IMPLEMENT_INTERFACE (MM_TYPE_IFACE_MODEM_3GPP, modem_3gpp_iface_init)
                        G_IMPLEMENT_INTERFACE (MM_TYPE_IFACE_MODEM_LOCATION, location_iface_init))

static void
read_radio (GTask *task,
            gpointer source_object,
            gpointer task_data,
            GCancellable *cancellable)
{
    const G965nWwanRequest request = GPOINTER_TO_UINT (task_data);
    g_autoptr(GDBusConnection) bus = NULL;
    g_autofree char *invocation = NULL;
    g_autoptr(JsonObject) reply = NULL;
    g_autoptr(GError) error = NULL;
    const char *field;
    JsonNode *node;
    gint64 value;

    (void) source_object;
    bus = g_bus_get_sync (G_BUS_TYPE_SYSTEM, cancellable, &error);
    if (!bus)
        goto failed;
    invocation = g965n_wwan_get_invocation (bus, cancellable, &error);
    if (!invocation)
        goto failed;
    reply = g965n_wwan_request (invocation, request, cancellable, &error);
    if (!reply)
        goto failed;
    if (request == G965N_WWAN_SIM_READINESS) {
        node = json_object_get_member (reply, "sim_ready");
        if (node && json_node_get_value_type (node) == G_TYPE_BOOLEAN) {
            g_task_return_int (task, json_node_get_boolean (node) ?
                               MM_MODEM_LOCK_NONE : MM_MODEM_LOCK_UNKNOWN);
            return;
        }
    } else if (request == G965N_WWAN_RADIO_STATE) {
        node = json_object_get_member (reply, "radio_state");
        if (node && json_node_get_value_type (node) == G_TYPE_STRING) {
            g_task_return_int (task, g_strcmp0 (json_node_get_string (node), "on") == 0 ?
                               MM_MODEM_POWER_STATE_ON : MM_MODEM_POWER_STATE_UNKNOWN);
            return;
        }
    }
    if (request == G965N_WWAN_SIM_READINESS || request == G965N_WWAN_RADIO_STATE) {
        g_task_return_new_error (task, MM_CORE_ERROR, MM_CORE_ERROR_FAILED,
                                 "SIPC modem did not return the requested state");
        return;
    }
    field = request == G965N_WWAN_REGISTRATION ? "registration_code" : "signal_rssi_code";
    node = json_object_get_member (reply, field);
    if (!node || json_node_get_value_type (node) != G_TYPE_INT64) {
        g_task_return_new_error (task, MM_CORE_ERROR, MM_CORE_ERROR_FAILED,
                                 "SIPC modem did not return %s", field);
        return;
    }
    value = json_node_get_int (node);
    if (request == G965N_WWAN_REGISTRATION && value >= 0 && value <= 10) {
        g_task_return_int (task, value);
        return;
    }
    if (request == G965N_WWAN_SIGNAL_QUALITY && value >= 0 && value <= 31) {
        g_task_return_int (task, (value * 100 + 15) / 31);
        return;
    }
    g_task_return_new_error (task, MM_CORE_ERROR, MM_CORE_ERROR_FAILED,
                             "SIPC modem returned unavailable %s", field);
    return;

failed:
    g_task_return_error (task, g_steal_pointer (&error));
}

static void
start_radio_query (MMIfaceModem *self,
                   G965nWwanRequest request,
                   GAsyncReadyCallback callback,
                   gpointer user_data)
{
    MMBaseModem *modem = MM_BASE_MODEM (self);
    g_autoptr(GTask) task = g_task_new (self, mm_base_modem_peek_cancellable (modem),
                                      callback, user_data);
    g_task_set_task_data (task, GUINT_TO_POINTER (request), NULL);
    g_task_run_in_thread (task, read_radio);
}

static void
load_capabilities (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    start_radio_query (self, G965N_WWAN_REGISTRATION, callback, user_data);
}

static MMModemCapability
load_capabilities_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    gssize state;

    g_assert (g_task_is_valid (result, self));
    state = g_task_propagate_int (G_TASK (result), error);
    return state < 0 ? MM_MODEM_CAPABILITY_NONE : MM_MODEM_CAPABILITY_LTE;
}

static void
load_supported_modes (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    g_autoptr(GTask) task = g_task_new (self, NULL, callback, user_data);
    GArray *modes = g_array_new (FALSE, FALSE, sizeof (MMModemModeCombination));
    const MMModemModeCombination mode = { MM_MODEM_MODE_4G, MM_MODEM_MODE_NONE };

    /* This describes the LTE-only SIPC backend, not all radio capabilities
     * of the chipset. Inherited ANY falsely includes 5G in GNOME Settings. */
    g_array_append_val (modes, mode);
    g_task_return_pointer (task, modes, (GDestroyNotify) g_array_unref);
}

static GArray *
load_supported_modes_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    g_assert (g_task_is_valid (result, self));
    return g_task_propagate_pointer (G_TASK (result), error);
}

static void
load_signal_quality (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    start_radio_query (self, G965N_WWAN_SIGNAL_QUALITY, callback, user_data);
}

static guint
load_signal_quality_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    gssize quality;

    g_assert (g_task_is_valid (result, self));
    quality = g_task_propagate_int (G_TASK (result), error);
    return quality < 0 ? 0 : (guint) quality;
}

static void
load_unlock_required (MMIfaceModem *self, gboolean last_attempt, GCancellable *cancellable,
                      GAsyncReadyCallback callback, gpointer user_data)
{
    g_autoptr(GTask) task = g_task_new (self, cancellable, callback, user_data);

    (void) last_attempt;
    g_task_set_task_data (task, GUINT_TO_POINTER (G965N_WWAN_SIM_READINESS), NULL);
    g_task_run_in_thread (task, read_radio);
}

static MMModemLock
load_unlock_required_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    gssize lock;

    g_assert (g_task_is_valid (result, self));
    lock = g_task_propagate_int (G_TASK (result), error);
    return lock < 0 ? MM_MODEM_LOCK_UNKNOWN : (MMModemLock) lock;
}

static void
load_power_state (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    start_radio_query (self, G965N_WWAN_RADIO_STATE, callback, user_data);
}

static MMModemPowerState
load_power_state_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    gssize state;

    g_assert (g_task_is_valid (result, self));
    state = g_task_propagate_int (G_TASK (result), error);
    return state < 0 ? MM_MODEM_POWER_STATE_UNKNOWN : (MMModemPowerState) state;
}

static void
create_sim (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    start_radio_query (self, G965N_WWAN_SIM_READINESS, callback, user_data);
}

static MMBaseSim *
create_sim_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    gssize state;

    g_assert (g_task_is_valid (result, self));
    state = g_task_propagate_int (G_TASK (result), error);
    if (state < 0)
        return NULL;
    if (state != MM_MODEM_LOCK_NONE) {
        g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_RETRY,
                             "Waiting for the SIPC modem to confirm SIM readiness");
        return NULL;
    }
    return mm_base_sim_new_initialized (MM_BASE_MODEM (self), 1, TRUE,
                                        NULL, NULL, NULL, NULL, NULL, NULL);
}

static void
load_ip_families (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    g_autoptr(GTask) task = g_task_new (self, NULL, callback, user_data);

    g_task_return_int (task, MM_BEARER_IP_FAMILY_IPV4);
}

static MMBearerIpFamily
load_ip_families_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    g_assert (g_task_is_valid (result, self));
    return g_task_propagate_int (G_TASK (result), error);
}

static void
create_bearer (MMIfaceModem *self, MMBearerProperties *properties,
               GAsyncReadyCallback callback, gpointer user_data)
{
    g_autoptr(GTask) task = g_task_new (self, NULL, callback, user_data);
    GError *error = NULL;
    MMBaseBearer *bearer = g965n_bearer_new (MM_BASE_MODEM (self), properties, &error);

    if (bearer)
        g_task_return_pointer (task, bearer, g_object_unref);
    else
        g_task_return_error (task, error);
}

static MMBaseBearer *
create_bearer_finish (MMIfaceModem *self, GAsyncResult *result, GError **error)
{
    g_assert (g_task_is_valid (result, self));
    return g_task_propagate_pointer (G_TASK (result), error);
}

/* SIPC cell identities; signal-unit fields remain intentionally unavailable. */
static void cell_list_free (GList *list) { g_list_free_full (list, g_object_unref); }

static void
cell_worker (GTask *task, gpointer source, gpointer data, GCancellable *cancel)
{
    g_autoptr(GDBusConnection) bus = NULL;
    g_autofree char *invocation = NULL;
    g_autoptr(JsonObject) reply = NULL;
    g_autoptr(GError) error = NULL;
    JsonArray *array;
    GList *list = NULL;
    guint i;
    (void) source; (void) data;
    bus = g_bus_get_sync (G_BUS_TYPE_SYSTEM, cancel, &error);
    if (!bus) goto failed;
    invocation = g965n_wwan_get_invocation (bus, cancel, &error);
    if (!invocation) goto failed;
    reply = g965n_wwan_request (invocation, G965N_WWAN_CELL_LIST, cancel, &error);
    if (!reply) goto failed;
    if (!json_object_has_member (reply, "requested")) goto unavailable;
    g_clear_pointer (&reply, json_object_unref);
    for (i = 0; i < 15; i++) {
        if (g_cancellable_set_error_if_cancelled (cancel, &error)) goto failed;
        reply = g965n_wwan_request (invocation, G965N_WWAN_CELL_INFO, cancel, &error);
        if (!reply) goto failed;
        if (json_object_has_member (reply, "cells")) break;
        g_clear_pointer (&reply, json_object_unref);
        g_usleep (200000);
    }
    if (!reply || !JSON_NODE_HOLDS_ARRAY (json_object_get_member (reply, "cells"))) goto unavailable;
    array = json_object_get_array_member (reply, "cells");
    if (json_array_get_length (array) > 64) goto unavailable;
    for (i = 0; i < json_array_get_length (array); i++) {
        JsonObject *row = json_array_get_object_element (array, i);
        MMCellInfo *cell;
        g_autofree char *tac = NULL, *ci = NULL, *pci = NULL;
        const char *operator_id;
        if (!row) goto unavailable;
        operator_id = json_object_get_string_member (row, "operator_id");
        if (!operator_id || strlen (operator_id) < 5 || strlen (operator_id) > 6 ||
            strspn (operator_id, "0123456789") != strlen (operator_id)) goto unavailable;
        cell = g_object_new (MM_TYPE_CELL_INFO_LTE, NULL);
        mm_cell_info_set_serving (cell, json_object_get_boolean_member (row, "serving"));
        mm_cell_info_lte_set_operator_id (MM_CELL_INFO_LTE (cell), operator_id);
        tac = g_strdup_printf ("%X", (guint) json_object_get_int_member (row, "tac"));
        ci = g_strdup_printf ("%X", (guint) json_object_get_int_member (row, "ci"));
        pci = g_strdup_printf ("%X", (guint) json_object_get_int_member (row, "pci"));
        mm_cell_info_lte_set_tac (MM_CELL_INFO_LTE (cell), tac);
        mm_cell_info_lte_set_ci (MM_CELL_INFO_LTE (cell), ci);
        mm_cell_info_lte_set_physical_ci (MM_CELL_INFO_LTE (cell), pci);
        if (json_object_has_member (row, "earfcn"))
            mm_cell_info_lte_set_earfcn (MM_CELL_INFO_LTE (cell), json_object_get_int_member (row, "earfcn"));
        list = g_list_append (list, cell);
    }
    g_task_return_pointer (task, list, (GDestroyNotify) cell_list_free);
    return;
unavailable:
    cell_list_free (list);
    g_task_return_new_error (task, MM_CORE_ERROR, MM_CORE_ERROR_FAILED, "No qualified fresh SIPC LTE cell reply");
    return;
failed:
    cell_list_free (list);
    g_task_return_error (task, g_steal_pointer (&error));
}

static void get_cells (MMIfaceModem *self, GAsyncReadyCallback callback, gpointer user_data)
{
    g_autoptr(GTask) task = g_task_new (self, mm_base_modem_peek_cancellable (MM_BASE_MODEM (self)), callback, user_data);
    g_task_run_in_thread (task, cell_worker);
}

static GList *get_cells_finish (MMIfaceModem *self, GAsyncResult *res, GError **error)
{
    g_assert (g_task_is_valid (res, self));
    return g_task_propagate_pointer (G_TASK (res), error);
}

static void location_cells_ready (GObject *object, GAsyncResult *res, gpointer unused)
{
    G965nModem *self = (G965nModem *) object;
    g_autoptr(GError) error = NULL;
    GList *list = get_cells_finish (MM_IFACE_MODEM (self), res, &error), *l;
    (void) unused;
    self->location_pending = FALSE;
    if (self->location_poll) {
        mm_iface_modem_location_3gpp_clear (MM_IFACE_MODEM_LOCATION (self));
        for (l = list; l; l = l->next) {
            MMCellInfoLte *cell = MM_CELL_INFO_LTE (l->data);
            if (!mm_cell_info_get_serving (l->data)) continue;
            mm_iface_modem_location_3gpp_update_operator_code (MM_IFACE_MODEM_LOCATION (self), mm_cell_info_lte_get_operator_id (cell));
            mm_iface_modem_location_3gpp_update_lac_tac_ci (MM_IFACE_MODEM_LOCATION (self), 0,
                g_ascii_strtoull (mm_cell_info_lte_get_tac (cell), NULL, 16),
                g_ascii_strtoull (mm_cell_info_lte_get_ci (cell), NULL, 16));
            break;
        }
    }
    cell_list_free (list);
}

static gboolean location_tick (gpointer data)
{
    G965nModem *self = data;
    if (!self->location_pending) {
        self->location_pending = TRUE;
        get_cells (MM_IFACE_MODEM (self), location_cells_ready, NULL);
    }
    return G_SOURCE_CONTINUE;
}

static void location_capabilities (MMIfaceModemLocation *self, GAsyncReadyCallback cb, gpointer data)
{
    g_autoptr(GTask) task = g_task_new (self, NULL, cb, data);
    g_task_return_int (task, MM_MODEM_LOCATION_SOURCE_3GPP_LAC_CI);
}
static MMModemLocationSource location_capabilities_finish (MMIfaceModemLocation *self, GAsyncResult *res, GError **error)
{ g_assert (g_task_is_valid (res, self)); return g_task_propagate_int (G_TASK (res), error); }
static void location_enable (MMIfaceModemLocation *iface, MMModemLocationSource source, GAsyncReadyCallback cb, gpointer data)
{
    G965nModem *self = (G965nModem *) iface;
    g_autoptr(GTask) task = g_task_new (self, NULL, cb, data);
    if (source != MM_MODEM_LOCATION_SOURCE_3GPP_LAC_CI) {
        g_task_return_new_error (task, MM_CORE_ERROR, MM_CORE_ERROR_UNSUPPORTED, "Only SIPC cell location is supported"); return;
    }
    if (!self->location_poll) self->location_poll = g_timeout_add_seconds (10, location_tick, self);
    location_tick (self);
    g_task_return_boolean (task, TRUE);
}
static void location_disable (MMIfaceModemLocation *iface, MMModemLocationSource source, GAsyncReadyCallback cb, gpointer data)
{
    G965nModem *self = (G965nModem *) iface;
    g_autoptr(GTask) task = g_task_new (self, NULL, cb, data);
    (void) source;
    if (self->location_poll) { g_source_remove (self->location_poll); self->location_poll = 0; }
    mm_iface_modem_location_3gpp_clear (iface);
    g_task_return_boolean (task, TRUE);
}
static gboolean location_toggle_finish (MMIfaceModemLocation *self, GAsyncResult *res, GError **error)
{ g_assert (g_task_is_valid (res, self)); return g_task_propagate_boolean (G_TASK (res), error); }
static void location_iface_init (MMIfaceModemLocation *iface)
{
    iface->load_capabilities = location_capabilities;
    iface->load_capabilities_finish = location_capabilities_finish;
    iface->enable_location_gathering = location_enable;
    iface->enable_location_gathering_finish = location_toggle_finish;
    iface->disable_location_gathering = location_disable;
    iface->disable_location_gathering_finish = location_toggle_finish;
}
static void cell_dispose (GObject *object)
{
    G965nModem *self = (G965nModem *) object;
    if (self->location_poll) { g_source_remove (self->location_poll); self->location_poll = 0; }
    G_OBJECT_CLASS (g965n_modem_parent_class)->dispose (object);
}

static void
modem_iface_init (MMIfaceModem *iface)
{
    iface->get_cell_info = get_cells;
    iface->get_cell_info_finish = get_cells_finish;
    iface->create_sim = create_sim;
    iface->create_sim_finish = create_sim_finish;
    iface->load_supported_ip_families = load_ip_families;
    iface->load_supported_ip_families_finish = load_ip_families_finish;
    iface->create_bearer = create_bearer;
    iface->create_bearer_finish = create_bearer_finish;
    iface->load_current_capabilities = load_capabilities;
    iface->load_current_capabilities_finish = load_capabilities_finish;
    iface->load_supported_modes = load_supported_modes;
    iface->load_supported_modes_finish = load_supported_modes_finish;
    iface->load_signal_quality = load_signal_quality;
    iface->load_signal_quality_finish = load_signal_quality_finish;
    iface->load_unlock_required = load_unlock_required;
    iface->load_unlock_required_finish = load_unlock_required_finish;
    iface->load_power_state = load_power_state;
    iface->load_power_state_finish = load_power_state_finish;
}

static void
run_registration_checks (MMIfaceModem3gpp *self, gboolean cs, gboolean ps,
                         gboolean eps, gboolean five_gs,
                         GAsyncReadyCallback callback, gpointer user_data)
{
    (void) cs;
    (void) ps;
    (void) eps;
    (void) five_gs;
    start_radio_query (MM_IFACE_MODEM (self), G965N_WWAN_REGISTRATION, callback, user_data);
}

static gboolean
run_registration_checks_finish (MMIfaceModem3gpp *self, GAsyncResult *result, GError **error)
{
    MMModem3gppRegistrationState state;
    MMModemAccessTechnology technology;
    gssize code;

    g_assert (g_task_is_valid (result, self));
    code = g_task_propagate_int (G_TASK (result), error);
    if (code < 0)
        return FALSE;
    switch (code) {
    case 0: state = MM_MODEM_3GPP_REGISTRATION_STATE_IDLE; break;
    case 1: state = MM_MODEM_3GPP_REGISTRATION_STATE_HOME; break;
    case 2: state = MM_MODEM_3GPP_REGISTRATION_STATE_SEARCHING; break;
    case 3: state = MM_MODEM_3GPP_REGISTRATION_STATE_DENIED; break;
    case 5: state = MM_MODEM_3GPP_REGISTRATION_STATE_ROAMING; break;
    default: state = MM_MODEM_3GPP_REGISTRATION_STATE_UNKNOWN; break;
    }
    technology = (code == 1 || code == 5) ? MM_MODEM_ACCESS_TECHNOLOGY_LTE :
                                           MM_MODEM_ACCESS_TECHNOLOGY_UNKNOWN;
    mm_iface_modem_3gpp_update_eps_registration_state (self, state, FALSE);
    mm_iface_modem_3gpp_update_access_technologies (self, technology);
    return TRUE;
}

static void
modem_3gpp_iface_init (MMIfaceModem3gpp *iface)
{
    iface->run_registration_checks = run_registration_checks;
    iface->run_registration_checks_finish = run_registration_checks_finish;
}

static void
g965n_modem_init (G965nModem *self)
{
    (void) self;
}

static void
g965n_modem_class_init (G965nModemClass *klass)
{
    MMBroadbandModemClass *broadband = MM_BROADBAND_MODEM_CLASS (klass);

    G_OBJECT_CLASS (klass)->dispose = cell_dispose;

    MM_BASE_MODEM_CLASS (klass)->native_control_with_net = TRUE;
    broadband->setup_ports = NULL;
    broadband->initialization_started = NULL;
    broadband->initialization_started_finish = NULL;
    broadband->initialization_stopped = NULL;
    broadband->enabling_started = NULL;
    broadband->enabling_started_finish = NULL;
}

#define MM_TYPE_PLUGIN_SAMSUNG_SIPC mm_plugin_samsung_sipc_get_type ()
MM_DEFINE_PLUGIN (SAMSUNG_SIPC, samsung_sipc, SamsungSipc)

static gboolean
is_native_control_port (MMPlugin *self, MMKernelDevice *port)
{
    static const char sysfs_path[] = "/sys/devices/platform/10000.mif_pdata/net/rmnet0";

    (void) self;
    return g_strcmp0 (mm_kernel_device_get_subsystem (port), "net") == 0 &&
           g_strcmp0 (mm_kernel_device_get_name (port), "rmnet0") == 0 &&
           g_strcmp0 (mm_kernel_device_get_sysfs_path (port), sysfs_path) == 0;
}

static MMBaseModem *
create_modem (MMPlugin *self, const gchar *uid, const gchar *physdev,
              const gchar **drivers, guint16 vendor, guint16 product,
              guint16 subsystem_vendor, GList *probes, GError **error)
{
    (void) vendor;
    (void) product;
    (void) subsystem_vendor;
    if (!probes || probes->next || !is_native_control_port (self, mm_port_probe_peek_port (probes->data))) {
        g_set_error_literal (error, MM_CORE_ERROR, MM_CORE_ERROR_UNSUPPORTED,
                             "Expected the physical G965N rmnet0 port");
        return NULL;
    }
    return g_object_new (g965n_modem_get_type (),
                         MM_BASE_MODEM_DEVICE, uid,
                         MM_BASE_MODEM_PHYSDEV, physdev,
                         MM_BASE_MODEM_DRIVERS, drivers,
                         MM_BASE_MODEM_PLUGIN, mm_plugin_get_name (self),
                         MM_BASE_MODEM_DATA_NET_SUPPORTED, TRUE,
                         MM_BASE_MODEM_DATA_TTY_SUPPORTED, FALSE,
                         NULL);
}

MM_PLUGIN_NAMED_CREATOR_SCOPE MMPlugin *
mm_plugin_create_samsung_sipc (void)
{
    static const gchar *subsystems[] = { "net", NULL };
    static const gchar *tags[] = { "ID_MM_G965N_SIPC", NULL };
    return MM_PLUGIN (g_object_new (MM_TYPE_PLUGIN_SAMSUNG_SIPC,
                                    MM_PLUGIN_NAME, MM_MODULE_NAME,
                                    MM_PLUGIN_ALLOWED_SUBSYSTEMS, subsystems,
                                    MM_PLUGIN_ALLOWED_UDEV_TAGS, tags,
                                    NULL));
}

static void
mm_plugin_samsung_sipc_init (MMPluginSamsungSipc *self)
{
    (void) self;
}

static void
mm_plugin_samsung_sipc_class_init (MMPluginSamsungSipcClass *klass)
{
    MMPluginClass *plugin = MM_PLUGIN_CLASS (klass);
    plugin->is_native_control_port = is_native_control_port;
    plugin->create_modem = create_modem;
}
