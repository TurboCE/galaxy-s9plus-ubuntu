/* SPDX-License-Identifier: GPL-2.0-only */
/* Original checked accounting for Broadcom SSI flow-control acknowledgements. */
#ifndef G965N_SSI_ACK_H
#define G965N_SSI_ACK_H
struct ssi_ack_state {
	unsigned int remaining, acknowledged;
};
static inline int ssi_ack_accept(struct ssi_ack_state *state, unsigned int count)
{
	if (count > state->remaining)
		return -EPROTO;
	state->remaining -= count;
	state->acknowledged += count;
	return 0;
}
static inline int ssi_ack_result(const struct ssi_ack_state *state, int result)
{
	if (result)
		return result;
	return state->remaining ? -ETIMEDOUT : 0;
}
#endif
