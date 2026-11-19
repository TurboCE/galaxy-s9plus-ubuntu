// SPDX-License-Identifier: MIT
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void reference(uint8_t *dst, const uint8_t *src,
                      const uint8_t swizzle[4], bool normalized, int count)
{
    for (int pixel = 0; pixel < count; ++pixel) {
        uint8_t t[] = {src[0], src[1], src[2], src[3], 0, normalized ? 255 : 1};
        for (int channel = 0; channel < 4; ++channel)
            dst[channel] = t[swizzle[channel]];
        dst += 4;
        src += 4;
    }
}

int main(void)
{
    uint8_t source[160], expected[160], result[160];
    for (unsigned i = 0; i < sizeof(source); ++i)
        source[i] = (i * 131 + 47) % 256;
    for (unsigned permutation = 0; permutation < 1296; ++permutation) {
        unsigned code = permutation;
        uint8_t swizzle[4];
        for (int channel = 0; channel < 4; ++channel) {
            swizzle[channel] = code % 6;
            code /= 6;
        }
        for (int normalized = 0; normalized < 2; ++normalized)
            for (int count = 0; count < 34; ++count) {
                memset(expected, 0xae, sizeof(expected));
                memset(result, 0xae, sizeof(result));
                reference(expected + 3, source + 1, swizzle, normalized, count);
                bool handled = swizzle_convert_ubyte4_neon(result + 3, source + 1,
                                                         swizzle, normalized, count);
                assert(handled == (count >= 4));
                if (!handled)
                    continue;
                assert(!memcmp(expected, result, sizeof(result)));

                memcpy(expected, source, sizeof(source));
                memcpy(result, source, sizeof(source));
                reference(expected + 1, expected + 1, swizzle, normalized, count);
                assert(swizzle_convert_ubyte4_neon(result + 1, result + 1,
                                                 swizzle, normalized, count));
                assert(!memcmp(expected, result, sizeof(result)));
            }
    }
    const uint8_t invalid[] = {0, 6, 2, 3};
    assert(!swizzle_convert_ubyte4_neon(result, source, invalid, true, 20));
    puts("1296 swizzles, both normalization modes, 0–33 pixels, unaligned and in-place pass");
}
