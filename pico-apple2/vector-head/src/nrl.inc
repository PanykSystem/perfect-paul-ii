; ---------------------------------------------------------------------------
; The NRL letter-to-sound rules on the 6502.
;
; The card cannot be read back -- the 74LVC245 faces one way and there is no
; status register -- so the Apple II cannot ask it what a sentence came out as.
; For the head to lip-sync text the operator types, it has to work the
; allophones out for itself.
;
; This is a transcription of nrl.c, deliberately literal, including the places
; where nrl.c is not what the 1976 report says: sibilant_at returns 1 for C and
; S before it ever looks for CH or SH, so a right context of & consumes one
; letter where a left context of & consumes two, and match_left has no % case
; at all.  Being bug-compatible is the whole point -- the firmware speaks what
; IT decides, and the mouth has to agree with the firmware, not the report.
;
; The tables are generated from nrl.c by mknrl_a2.py, so a rule fixed in the
; firmware is fixed here by rebuilding.  Only the code is written twice, and
; nrltest.py is what checks the two agree: it runs both over a word list and
; requires the allophone streams to be identical.
; ---------------------------------------------------------------------------

CL_VOWEL   = 1
CL_CONS    = 2
CL_VOICED  = 4
CL_FRONT   = 8

PH_VOWEL   = 1
PH_FRONT   = 2
PH_PLOSIVE = 4

; A set of characters, tested with a cmp chain: short enough that a loop would
; cost more than it saves, and it keeps each set beside its C original.
.macro ONEOF chars, target
        .repeat .strlen(chars), i
        cmp #.strat(chars, i)
        beq target
        .endrepeat
.endmacro

; ---------------------------------------------------------------------------
; nrl_init -- the 256-byte class table, so a class test is one indexed load
; and does not need a register the matchers are already using.
; ---------------------------------------------------------------------------
nrl_init:
        lda #0
        tax
@zero:  sta cls256,x
        inx
        bne @zero
        ldx #0
@set:   lda nrl_class,x
        sta cls256+'A',x
        inx
        cpx #26
        bne @set
        rts

; A = character; C set if it is a letter.  X and Y untouched.
nrl_isletter:
        cmp #'A'
        bcc @no
        cmp #'Z'+1
        bcs @no
        sec
        rts
@no:    clc
        rts

; ---------------------------------------------------------------------------
; nrl_say -- work (NUL-terminated, upper case) -> allo / an.
; ---------------------------------------------------------------------------
nrl_say:
        jsr nrl_fix
        jsr nrl_stage1
        jmp nrl_stage2

; ---------------------------------------------------------------------------
; nrl_fix -- substitute whole words from the exception table, in place.
;
; A word is what stands between characters that are not letters, so a full stop
; after a word does not hide it from the table.  A substitution is stepped over
; rather than rescanned, which is what prepare() in nrl.c does by building its
; output as it goes -- otherwise HI -> HIGH would be looked up again.
; ---------------------------------------------------------------------------
nrl_fix:
        ldx #0                  ; upper case first, as prepare() does: a //e
@up:    lda work,x              ; can type lower case and the rules are all
        beq @upd                ; written in capitals
        cmp #'a'
        bcc @nextup
        cmp #'z'+1
        bcs @nextup
        sec
        sbc #$20
        sta work,x
@nextup:
        inx
        jmp @up
@upd:   lda #0
        sta wi
@scan:  ldx wi
        lda work,x
        beq @done
        jsr nrl_isletter
        bcs @word
        cmp #'0'                ; a digit becomes its word, spaces and all
        bcc @skip1
        cmp #'9'+1
        bcs @skip1
        jsr nrl_digit
        lda wi
        clc
        adc saidlen
        sta wi
        jmp @scan
@skip1: inc wi
        jmp @scan
@word:  ldx wi
        ldy #0
@len:   lda work,x
        jsr nrl_isletter
        bcc @have
        inx
        iny
        jmp @len
@have:  sty wlen
        jsr nrl_lookup
        bcs @splice
        lda wi                  ; not in the table: step over the word
        clc
        adc wlen
        sta wi
        jmp @scan
@splice:
        jsr nrl_splice
        lda wi
        clc
        adc saidlen
        sta wi
        jmp @scan
@done:  rts

; ---------------------------------------------------------------------------
; nrl_digit -- A = the digit character; splice " WORD " in over it.
; ---------------------------------------------------------------------------
nrl_digit:
        sec
        sbc #'0'
        tax
        lda nrl_digit_off,x
        clc
        adc #<nrl_digits
        sta fixp
        lda #0
        adc #>nrl_digits
        sta fixp+1
        ldy #0
        lda (fixp),y            ; the length byte sits in front of the text
        sta saidlen
        inc fixp
        bne :+
        inc fixp+1
:       lda #1
        sta wlen                ; one character replaced
        jmp nrl_splice

; ---------------------------------------------------------------------------
; nrl_lookup -- is work[wi..wi+wlen) in the table?
; C set, and fixp left pointing at the replacement, with saidlen set.
; ---------------------------------------------------------------------------
nrl_lookup:
        lda #<nrl_fixes
        sta fixp
        lda #>nrl_fixes
        sta fixp+1
@entry: ldy #0
        lda (fixp),y
        beq @no                 ; end of table
        cmp wlen
        bne @next
        iny                     ; same length: compare the letters
        lda (fixp),y
        sta saidlen
        ldy #2
        ldx wi
        lda wlen
        sta tmp1
@cmp:   lda (fixp),y
        cmp work,x
        bne @next
        iny
        inx
        dec tmp1
        bne @cmp
        tya                     ; matched: fixp += 2 + wlen, i.e. += y
        clc
        adc fixp
        sta fixp
        bcc @set
        inc fixp+1
@set:   sec
        rts
@next:  ldy #0                  ; fixp += 2 + lenWord + lenSaid
        lda (fixp),y
        sta tmp1
        iny
        lda (fixp),y
        clc
        adc tmp1
        clc
        adc #2
        clc
        adc fixp
        sta fixp
        bcc @entry
        inc fixp+1
        jmp @entry
@no:    clc
        rts

; ---------------------------------------------------------------------------
; nrl_splice -- replace work[wi..wi+wlen) with saidlen bytes at (fixp).
;
; The tail is parked and put back rather than shuffled in place.  A replacement
; may be longer or shorter than the word (HI -> HIGH, LIVE -> LIV), and an
; in-place shuffle has to go in opposite directions for the two cases; this
; does not care, and the buffer is 128 bytes, so the copy costs nothing worth
; the risk of getting that backwards.
; ---------------------------------------------------------------------------
nrl_splice:
        lda wi                  ; park everything after the word
        clc
        adc wlen
        tay
        ldx #0
@save:  lda work,y
        sta tail,x
        beq @saved
        iny
        inx
        jmp @save
@saved: ldy #0                  ; drop the replacement in
        ldx wi
        lda saidlen
        beq @back
        sta tmp1
@copy:  lda (fixp),y
        sta work,x
        iny
        inx
        dec tmp1
        bne @copy
@back:  ldy #0                  ; and the tail after it
@tl:    lda tail,y
        sta work,x
        beq @done
        iny
        inx
        jmp @tl
@done:  rts

; ---------------------------------------------------------------------------
; nrl_stage1 -- letters to phonemes.
;
; For each position: pick the group by the character, walk its rules in order,
; and take the first whose literal, left context and right context all match.
; The groups are ordered longest-and-most-specific first with the bare letter
; last, which is what makes "first match wins" the whole of the control flow.
; ---------------------------------------------------------------------------
nrl_stage1:
        lda #0
        sta wi
        sta pn
@char:  ldx wi
        lda work,x
        JEQ @done
        jsr nrl_group
@rule:  ldy #0
        lda (rp),y
        cmp #$FF
        beq @skip
        sta lenL
        ldy #1
        lda (rp),y
        sta lenM
        iny
        lda (rp),y
        sta lenR
        iny
        lda (rp),y
        sta lenO
        lda #4                  ; where each field starts within the rule
        clc
        adc lenL
        sta moff
        clc
        adc lenM
        sta roff
        clc
        adc lenR
        sta ooff

        ldy moff                ; the literal, first, as strncmp does
        ldx wi
        lda lenM
        beq @left
        sta tmp1
@mcmp:  lda (rp),y
        cmp work,x
        bne @next
        iny
        inx
        dec tmp1
        bne @mcmp
@left:  jsr nrl_left
        bcc @next
        jsr nrl_right
        bcc @next
        jsr nrl_emit
        lda wi
        clc
        adc lenM
        sta wi
        jmp @char
@next:  lda ooff                ; on to the next rule in the group
        clc
        adc lenO
        clc
        adc rp
        sta rp
        bcc @rule
        inc rp+1
        jmp @rule
@skip:  inc wi                  ; nothing matched: drop the character
        jmp @char
@done:  rts

; A = character -> rp = the first rule of its group.
nrl_group:
        jsr nrl_isletter
        bcs @letter
        ldx #26*2               ; punctuation is the last group
        bne @have
@letter:
        sec
        sbc #'A'
        asl
        tax
@have:  lda nrl_group_tab,x
        clc
        adc #<nrl_rules
        sta rp
        lda nrl_group_tab+1,x
        adc #>nrl_rules
        sta rp+1
        rts

; Append this rule's output phonemes.
nrl_emit:
        lda lenO
        beq @done
        sta tmp1
        ldy ooff
        ldx pn
@loop:  cpx #PH_MAX
        bcs @stop
        lda (rp),y
        sta ph,x
        iny
        inx
        dec tmp1
        bne @loop
@stop:  stx pn
@done:  rts

; ---------------------------------------------------------------------------
; nrl_right -- the right context, walked forward from just past the literal.
; C set on a match.
; ---------------------------------------------------------------------------
nrl_right:
        lda roff
        sta pidx
        clc
        adc lenR
        sta pend
        lda wi
        clc
        adc lenM
        tax
@loop:  lda pidx
        cmp pend
        beq @ok
        ldy pidx
        inc pidx
        lda (rp),y
        cmp #' '
        beq @spc
        cmp #'#'
        beq @vowel
        cmp #':'
        beq @cons0
        cmp #'^'
        beq @cons1
        cmp #'.'
        beq @voiced
        cmp #'+'
        beq @front
        cmp #'%'
        beq @suffix
        cmp #'&'
        beq @sib
        cmp #'@'
        beq @longu
        cmp work,x              ; a literal
        bne @fail
        inx
        jmp @loop
@ok:    sec
        rts
@fail:  clc
        rts

@spc:   ldy work,x              ; a boundary, and it consumes nothing
        lda cls256,y
        and #CL_VOWEL|CL_CONS
        bne @fail
        jmp @loop
@vowel: ldy work,x
        lda cls256,y
        and #CL_VOWEL
        beq @fail
@vrun:  ldy work,x
        lda cls256,y
        and #CL_VOWEL
        beq @loop
        inx
        jmp @vrun
@cons0: ldy work,x              ; zero or more consonants
        lda cls256,y
        and #CL_CONS
        beq @loop
        inx
        jmp @cons0
@cons1: ldy work,x
        lda cls256,y
        and #CL_CONS
        beq @fail
        inx
        jmp @loop
@voiced:ldy work,x
        lda cls256,y
        and #CL_VOICED
        beq @fail
        inx
        jmp @loop
@front: ldy work,x
        lda cls256,y
        and #CL_FRONT
        beq @fail
        inx
        jmp @loop
@suffix:jsr nrl_suffix
        beq @fail
        jmp @advance
@sib:   jsr nrl_sib
        beq @fail
        jmp @advance
@longu: jsr nrl_longu
        beq @fail
@advance:
        stx tmp1                ; X += A
        clc
        adc tmp1
        tax
        jmp @loop

; ---------------------------------------------------------------------------
; nrl_left -- the left context, walked BACKWARDS from the character before the
; literal, which is why the patterns read left to right in the table.
;
; X runs below zero at the start of the line and wraps to $80 and above, which
; is the "i < 0" of the C.  The work buffer is capped at 120 characters so the
; two can never be confused.
; ---------------------------------------------------------------------------
nrl_left:
        lda lenL
        beq @ok
        clc
        adc #4
        sta pidx                ; one past the end; pre-decremented below
        ldx wi
        dex
@loop:  lda pidx
        cmp #4
        beq @ok
        dec pidx
        ldy pidx
        lda (rp),y
        cmp #' '
        beq @spc
        cmp #'#'
        beq @vowel
        cmp #':'
        beq @cons0
        cmp #'^'
        beq @cons1
        cmp #'.'
        beq @voiced
        cmp #'+'
        JEQ @front
        cmp #'&'
        JEQ @sib
        cmp #'@'
        JEQ @longu
        cpx #$80                ; a literal, and there must be a character
        bcs @fail
        cmp work,x
        bne @fail
        dex
        jmp @loop
@ok:    sec
        rts
@fail:  clc
        rts

@spc:   cpx #$80                ; off the front is a boundary, and consumes
        bcs @loop               ; nothing either way
        ldy work,x
        lda cls256,y
        and #CL_VOWEL|CL_CONS
        bne @fail
        jmp @loop
@vowel: cpx #$80
        bcs @fail
        ldy work,x
        lda cls256,y
        and #CL_VOWEL
        beq @fail
@vrun:  cpx #$80
        bcs @loop
        ldy work,x
        lda cls256,y
        and #CL_VOWEL
        beq @loop
        dex
        jmp @vrun
@cons0: cpx #$80
        bcs @loop
        ldy work,x
        lda cls256,y
        and #CL_CONS
        JEQ @loop
        dex
        jmp @cons0
@cons1: cpx #$80
        bcs @fail
        ldy work,x
        lda cls256,y
        and #CL_CONS
        beq @fail
        dex
        jmp @loop
@voiced:cpx #$80
        bcs @fail
        ldy work,x
        lda cls256,y
        and #CL_VOICED
        beq @fail
        dex
        jmp @loop
@front: cpx #$80
        bcs @fail
        ldy work,x
        lda cls256,y
        and #CL_FRONT
        beq @fail
        dex
        jmp @loop

; Unlike the right context, this one does know about the CH/SH and CH/TH/SH
; digraphs -- see the note at the top.
@sib:   cpx #$80
        JCS @fail
        cpx #1
        bcc @sib1
        lda work,x
        cmp #'H'
        bne @sib1
        dex
        lda work,x
        ONEOF "CS", @took2
        inx
@sib1:  jsr nrl_sib
        JEQ @fail
        dex
        jmp @loop
@took2: dex
        jmp @loop

@longu: cpx #$80
        JCS @fail
        cpx #1
        bcc @lu1
        lda work,x
        cmp #'H'
        bne @lu1
        dex
        lda work,x
        ONEOF "TCS", @took2
        inx
@lu1:   jsr nrl_longu
        JEQ @fail
        dex
        jmp @loop

; ---------------------------------------------------------------------------
; The character classes that need more than one letter.  X = index into work,
; A = how many characters were consumed, 0 for no match.
; ---------------------------------------------------------------------------
nrl_suffix:                     ; E ER ES ED ING ELY
        lda work,x
        cmp #'I'
        bne @notI
        lda work+1,x
        cmp #'N'
        bne @zero
        lda work+2,x
        cmp #'G'
        bne @zero
        lda #3
        rts
@notI:  cmp #'E'
        bne @zero
        lda work+1,x
        cmp #'L'
        bne @e2
        lda work+2,x
        cmp #'Y'
        bne @e2
        lda #3
        rts
@e2:    lda work+1,x
        ONEOF "RSD", @two
        lda #1
        rts
@two:   lda #2
        rts
@zero:  lda #0
        rts

; S C G Z X J.  nrl.c returns 1 for C and S before it ever tests for CH or SH,
; so the two-character case below it is unreachable; kept unreachable here.
nrl_sib:
        lda work,x
        ONEOF "SCGZXJ", @one
        lda #0
        rts
@one:   lda #1
        rts

nrl_longu:                      ; T S R D L Z N J, and CH
        lda work,x
        ONEOF "TSRDLZNJ", @one
        ONEOF "TCS", @two       ; only C can reach here
        lda #0
        rts
@two:   lda work+1,x
        cmp #'H'
        bne @zero
        lda #2
        rts
@one:   lda #1
        rts
@zero:  lda #0
        rts

; ---------------------------------------------------------------------------
; nrl_stage2 -- phonemes to AL2, which is where the chip's positional variants
; get chosen.  Transcribed from nrl.c; the data sheet's own example words are
; in the comments there.
; ---------------------------------------------------------------------------
nrl_stage2:
        jsr nrl_gem
        lda #0
        sta an
        sta i2

@loop:  lda i2
        cmp pn
        JCS @end
        ldx i2
        lda ph,x
        sta cur
        lda #P_BOUND            ; prev, or a boundary at the start
        sta prev
        ldx i2
        beq @noprev
        dex
        lda ph,x
        sta prev
@noprev:
        lda #P_BOUND            ; next, or a boundary at the end
        sta nextp
        ldx i2
        inx
        cpx pn
        bcs @nonext
        lda ph,x
        sta nextp
@nonext:
        lda cur                 ; a boundary of its own is a pause
        cmp #P_BOUND
        bne @notb
        lda #A_PA3
        jsr nrl_put
        jmp @adv
@notb:
        ; Vowel + r, before anything else, because it replaces two phonemes
        ; with one allophone.  Only when the r closes the syllable: an r
        ; between two vowels is the next syllable's onset and stays a real RR,
        ; or VERY becomes "vairy" and SORRY "sarry".
        ldx cur
        lda ph_class,x
        and #PH_VOWEL
        beq @novr
        lda nextp
        cmp #P_r
        bne @novr
        lda i2
        clc
        adc #2
        cmp pn
        bcs @vrok               ; nothing after the r
        tax
        lda ph,x
        tax
        lda ph_class,x
        and #PH_VOWEL
        bne @novr
@vrok:  lda cur
        cmp #P_AO
        beq @vror
        cmp #P_OW
        beq @vror
        cmp #P_AA
        beq @vrar
        cmp #P_AH
        beq @vrar
        cmp #P_IY
        beq @vryr
        cmp #P_IH
        beq @vryr
        cmp #P_EH
        beq @vrxr
        cmp #P_EY
        beq @vrxr
        cmp #P_AE
        beq @vrxr
        jmp @novr               ; AY AW OY UW keep a real r after them
@vror:  lda #A_OR
        bne @vrput
@vrar:  lda #A_AR
        bne @vrput
@vryr:  lda #A_YR
        bne @vrput
@vrxr:  lda #A_XR
@vrput: jsr nrl_put
        inc i2                  ; and swallow the r
        jmp @adv
@novr:
        ; A plosive needs a pause in front of it or its burst is inaudible.
        ldx cur
        lda ph_class,x
        and #PH_PLOSIVE
        beq @nopl
        lda prev
        cmp #P_BOUND
        bne @pa1
        lda #A_PA2
        bne @plput
@pa1:   lda #A_PA1
@plput: jsr nrl_put
@nopl:
        ldx cur                 ; the ones position does not decide
        lda ph_al2,x
        cmp #$FF
        beq @special
        jsr nrl_put
        jmp @adv

@special:
        lda cur
        cmp #P_UW
        beq @uw
        cmp #P_ER
        beq @er
        cmp #P_b
        JEQ @b
        cmp #P_t
        JEQ @t
        cmp #P_d
        JEQ @d
        cmp #P_k
        JEQ @k
        cmp #P_g
        JEQ @g
        cmp #P_DH
        JEQ @dh
        cmp #P_h
        JEQ @h
        cmp #P_n
        JEQ @n
        cmp #P_l
        JEQ @l
        cmp #P_y
        JEQ @y
        cmp #P_r
        JEQ @r
        jmp @adv                ; P_NONE and anything unmapped

        ; UW1 is the short "to", UW2 the long "food".  The rules do not mark
        ; stress, so length comes from position: a final or pre-consonant /u/
        ; carries the syllable and gets the long one.
@uw:    lda nextp
        cmp #P_BOUND
        beq @uw2
        ldx nextp
        lda ph_class,x
        and #PH_VOWEL
        bne @uw1
@uw2:   lda #A_UW2
        JNE @put
@uw1:   lda #A_UW1
        JNE @put

        ; ER1 is the unstressed "letter" ending, ER2 the stressed "fir".
@er:    lda nextp
        cmp #P_BOUND
        bne @er2
        lda i2
        cmp #2
        bcc @er2
        lda #A_ER1
        JNE @put
@er2:   lda #A_ER2
        JNE @put

@b:     lda prev
        cmp #P_BOUND
        beq @bb1
        lda #A_BB2
        JNE @put
@bb1:   lda #A_BB1
        JNE @put

@t:     lda nextp
        cmp #P_BOUND
        beq @tt1
        lda #A_TT2
        JNE @put
@tt1:   lda #A_TT1
        JNE @put

@d:     lda prev
        cmp #P_BOUND
        beq @dd2
        lda #A_DD1
        JNE @put
@dd2:   lda #A_DD2
        JNE @put

        ; A /k/ not followed by a vowel is in a cluster (CLEAR), and so is one
        ; not preceded by a vowel inside a word (SKY); only a /k/ that both
        ; opens a syllable and leads to a vowel gets KK1 or KK3, chosen by
        ; whether that vowel is front.
@k:     ldx nextp
        lda ph_class,x
        and #PH_VOWEL
        beq @kk2
        lda prev
        cmp #P_BOUND
        beq @kfront
        ldx prev
        lda ph_class,x
        and #PH_VOWEL
        beq @kk2
@kfront:
        ldx nextp
        lda ph_class,x
        and #PH_FRONT
        beq @kk3
        lda #A_KK1
        JNE @put
@kk3:   lda #A_KK3
        JNE @put
@kk2:   lda #A_KK2
        JNE @put

@g:     lda nextp
        cmp #P_BOUND
        beq @gg3
        ldx nextp
        lda ph_class,x
        and #PH_FRONT
        beq @gg1
        lda #A_GG2
        bne @put
@gg1:   lda #A_GG1
        bne @put
@gg3:   lda #A_GG3
        bne @put

@dh:    lda prev
        cmp #P_BOUND
        beq @dh1
        lda #A_DH2
        bne @put
@dh1:   lda #A_DH1
        bne @put

@h:     ldx nextp
        lda ph_class,x
        and #PH_FRONT
        beq @hh2
        lda #A_HH1
        bne @put
@hh2:   lda #A_HH2
        bne @put

@n:     lda prev
        cmp #P_BOUND
        beq @nn2
        lda #A_NN1
        bne @put
@nn2:   lda #A_NN2
        bne @put

        ; EL is the syllabic l of "saddle": word-final after a consonant.
@l:     lda nextp
        cmp #P_BOUND
        bne @ll
        ldx prev
        lda ph_class,x
        and #PH_VOWEL
        bne @ll
        lda #A_EL
        bne @put
@ll:    lda #A_LL
        bne @put

@y:     lda prev
        cmp #P_BOUND
        beq @yy2
        lda #A_YY1
        bne @put
@yy2:   lda #A_YY2
        bne @put

        ; RR2 is the "brain" r, inside a consonant cluster.
@r:     lda prev
        cmp #P_BOUND
        beq @rr1
        ldx prev
        lda ph_class,x
        and #PH_VOWEL
        bne @rr1
        lda #A_RR2
        bne @put
@rr1:   lda #A_RR1

@put:   jsr nrl_put
@adv:   inc i2
        jmp @loop

@end:   lda #A_PA5              ; let the last sound finish
        jmp nrl_put

; ---------------------------------------------------------------------------
; nrl_gem -- drop a repeated consonant.
;
; A respelling that doubles a consonant to force a short vowel -- BIZZY,
; WIMMIN, DIJJIT, the trick the exception table is built on -- also asks the
; chip to say that consonant twice, which it audibly does.  English has no
; geminate inside a word.  A word boundary between the two is itself a repeat
; of P_BOUND and collapses the same way, which is what nrl.c does.
; ---------------------------------------------------------------------------
nrl_gem:
        lda #0
        sta i2                  ; read cursor
        sta gw                  ; write cursor
@loop:  lda i2
        cmp pn
        bcs @done
        ldx i2
        lda ph,x
        sta cur
        ldx gw
        beq @keep               ; nothing written yet
        dex
        lda ph,x
        cmp cur
        bne @keep
        ldx cur
        lda ph_class,x
        and #PH_VOWEL
        beq @drop
@keep:  ldx gw
        lda cur
        sta ph,x
        inc gw
@drop:  inc i2
        jmp @loop
@done:  lda gw
        sta pn
        rts

; Append A to the allophone list.
nrl_put:
        ldx an
        cpx #ALLO_MAX
        bcs @full
        sta allo,x
        inc an
@full:  rts
