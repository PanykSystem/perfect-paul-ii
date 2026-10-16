; A harness: put text in `work`, call nrl_say, read `allo`/`an`.
; nrldata.bin must be loaded at NRL_ORG alongside this.
        .include "jbranch.inc"
        .include "nrlzp.inc"
        .include "nrlsym.inc"
NRLBUF = $8000

        .org $6000
        .export nrl_say, nrl_init, work, allo, an, ph, pn
start:  jsr nrl_init
        jsr nrl_say
        rts

        .include "nrl.inc"
        .include "nrlbuf.inc"
