/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G965N_BEARER_H
#define G965N_BEARER_H

#include "mm-base-bearer.h"

MMBaseBearer *g965n_bearer_new (MMBaseModem *modem, MMBearerProperties *properties,
                              GError **error);
#endif
