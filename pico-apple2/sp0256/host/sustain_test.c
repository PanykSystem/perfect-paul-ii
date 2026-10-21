/* Does the core sustain after the sequencer halts?  Perfect Paul ][, GPL-3. */
#include <stdio.h>
#include "sp0256.h"
#include "sp0256_speak.h"

int main(void)
{
    int i, nz = 0, halted_at = -1;
    sp0256_speak_init();
    sp0256_speak_push(7);                       /* EH */

    for (i = 0; i < 20000; i++) {               /* 2 s at 10 kHz */
        const int16_t v = sp0256_speak_next_sample();
        if (halted_at < 0 && sp0256_halted() && i > 100) halted_at = i;
        if (halted_at >= 0 && i > halted_at + 2000 && v) nz++;
    }
    printf("halted at sample %d; %d non-zero samples well after that\n",
           halted_at, nz);
    puts(nz > 100 ? "  sustaining -- the real part's behaviour"
                  : "  SILENT after halt -- the fix is not active");

    /* init first: it resets the core, and the reset turns sustain back on */
    sp0256_speak_init();
    sp0256_set_sustain(0);
    sp0256_speak_push(7);
    nz = 0; halted_at = -1;
    for (i = 0; i < 20000; i++) {
        const int16_t v = sp0256_speak_next_sample();
        if (halted_at < 0 && sp0256_halted() && i > 100) halted_at = i;
        if (halted_at >= 0 && i > halted_at + 2000 && v) nz++;
    }
    printf("with sustain off: %d non-zero samples after halt%s\n", nz,
           nz == 0 ? "  (the old behaviour, exactly)" : "  -- UNEXPECTED");
    return 0;
}
