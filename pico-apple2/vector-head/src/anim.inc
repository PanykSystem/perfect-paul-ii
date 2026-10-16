; ---------------------------------------------------------------------------
; Turning a list of allophones into a lip-sync, at run time.
;
; mkscript2.py did this on the PC for the one canned sentence.  With text
; typed at the machine there is nothing to precompute, so the same model runs
; here: the costs are the ones run2.py measured, the durations are the ones
; pp2_render measured, and the arithmetic is in quarter milliseconds so that
; adding four seconds of allophones up does not wander.
;
; The one improvement on doing it on the PC is that the delays are worked out
; as the animation runs, from what the frame actually cost rather than from
; what it was predicted to cost.  The page about to be drawn into is two
; frames behind the screen, so whether a shape needs copying is a question
; about that page; here the loop simply asks it, and charges itself for what
; it did.
; ---------------------------------------------------------------------------

MOUTH4  = 35                    ; blit_mouth, 8.701 ms, in quarter ms
EYE4    = 16                    ; blit_eye,   3.979 ms
LOOP4   = 1                     ; the frame loop's own work
AUDIO_LAT4 = 77                 ; the card is 19.3 ms behind the byte

; A blink is open -> half -> shut -> half -> open.  The gaps cycle rather than
; repeat so it does not look metronomic.
BLINK_HALF = 200                ; 50 ms
BLINK_SHUT = 320                ; 80 ms
SOUND_CAP  = $F000              ; stop laying frames before the clock wraps

blink_gaps:
        .word 9200, 14800, 11600, 17200         ; 2.3 3.7 2.9 4.3 seconds

; ---------------------------------------------------------------------------
; build_frames -- allo/an -> fvis, feye, fsound, nf.
;
; One frame per change of either shape.  fsound[f] is when frame f is due,
; measured from the moment the card is handed the first allophone.
; ---------------------------------------------------------------------------
build_frames:
        lda #0
        sta nf
        sta k
        sta blink_ph
        sta blink_gi
        sta eyenow
        lda #$FF
        sta lastv
        sta laste
        lda #<AUDIO_LAT4
        sta sound
        lda #>AUDIO_LAT4
        sta sound+1
        lda #<(AUDIO_LAT4+9200)         ; the first blink
        sta blink_at
        lda #>(AUDIO_LAT4+9200)
        sta blink_at+1
        lda #1
        sta blink_gi

@each:  lda k
        cmp an
        JCS @done
        lda sound+1                     ; the clock is about to wrap: stop
        cmp #>SOUND_CAP
        bcs @done

@blink: lda sound+1                     ; any blink events due by now?
        cmp blink_at+1
        bcc @noblink
        bne @step
        lda sound
        cmp blink_at
        bcc @noblink
@step:  jsr blink_step
        jmp @blink
@noblink:
        ldx k                           ; the mouth this allophone wants
        lda allo,x
        tax
        lda allo_viseme,x
        sta vnow
        cmp lastv
        bne @emit
        lda eyenow
        cmp laste
        beq @hold
@emit:  ldx nf
        cpx #FRAME_MAX
        bcs @hold
        lda vnow
        sta fvis,x
        sta lastv
        lda eyenow
        sta feye,x
        sta laste
        txa                             ; fsound is 16-bit
        asl
        tax
        lda sound
        sta fsound,x
        lda sound+1
        sta fsound+1,x
        inc nf
@hold:  ldx k                           ; sound += this allophone's duration
        lda allo,x
        tax
        clc
        lda sound
        adc allo_dur4,x
        sta sound
        lda sound+1
        adc allo_dur4h,x
        sta sound+1
        inc k
        jmp @each

@done:  ldx nf                          ; one past the end: when it all stops
        txa
        asl
        tax
        lda sound
        sta fsound,x
        lda sound+1
        sta fsound+1,x
        rts

; ---------------------------------------------------------------------------
; blink_step -- the next event in a blink, and when the one after it is due.
; ---------------------------------------------------------------------------
blink_step:
        lda blink_ph
        beq @close1
        cmp #1
        beq @shut
        cmp #2
        beq @close2
        lda #0                          ; phase 3: open again
        sta eyenow
        sta blink_ph
        lda blink_gi                    ; and the next gap in the cycle
        asl
        tax
        lda blink_gaps,x
        ldy blink_gaps+1,x
        jsr blink_add
        inc blink_gi
        lda blink_gi
        and #3
        sta blink_gi
        rts
@close1:
        lda #1
        sta eyenow
        inc blink_ph
        lda #<BLINK_HALF
        ldy #>BLINK_HALF
        jmp blink_add
@shut:  lda #2
        sta eyenow
        inc blink_ph
        lda #<BLINK_SHUT
        ldy #>BLINK_SHUT
        jmp blink_add
@close2:
        lda #1
        sta eyenow
        inc blink_ph
        lda #<BLINK_HALF
        ldy #>BLINK_HALF
        jmp blink_add

blink_add:                              ; blink_at += A/Y
        clc
        adc blink_at
        sta blink_at
        tya
        adc blink_at+1
        sta blink_at+1
        rts

; ---------------------------------------------------------------------------
; run_frames -- hand the card the sentence, then follow it.
; ---------------------------------------------------------------------------
run_frames:
        lda #MODEALLO                   ; the card may have been left in text
        sta SLOT4
        ldx #0
@send:  cpx an
        beq @sent
        lda allo,x
        ora #RAWBASE
        sta SLOT4
        ; The card's PIO receiver is eight deep and core 0 does nothing but
        ; drain it, so this is belt and braces.  About 200 us a byte, which
        ; gives the receiver 1.6 ms of slack and still puts a long sentence
        ; across in under 40 ms.  Worth it: a dropped allophone cannot be
        ; detected from this side and would desync the mouth for good.
        ldy #40
@pace:  dey
        bne @pace
        inx
        jmp @send
@sent:
        lda an                          ; screen = an * 0.875 quarter ms
        lsr
        lsr
        lsr
        sta tmp1
        lda an
        sec
        sbc tmp1
        sta screen
        lda #0
        sta screen+1
        sta f

@frame: lda f
        cmp nf
        JCS @done
        lda #LOOP4                      ; what this frame costs
        sta cost

        ldx f
        lda fvis,x
        ldy hidx
        cmp curmouth,y
        beq @eyes
        sta curmouth,y
        tax
        jsr blit_mouth
        clc
        lda cost
        adc #MOUTH4
        sta cost
@eyes:  ldx f
        lda feye,x
        ldy hidx
        cmp cureye,y
        beq @up
        sta cureye,y
        tax
        jsr blit_eye
        clc
        lda cost
        adc #EYE4
        sta cost
@up:    jsr flip                        ; this frame is now on the screen
        clc
        lda screen
        adc cost
        sta screen
        lda screen+1
        adc #0
        sta screen+1

        ; What will the NEXT frame cost?  flip has already swapped hidx, so
        ; the same question asked of the same variable answers for the page
        ; the next frame will be drawn into.
        lda #LOOP4
        sta cost
        inc f
        lda f
        cmp nf
        bcs @tail
        ldx f
        lda fvis,x
        ldy hidx
        cmp curmouth,y
        beq @e2
        clc
        lda cost
        adc #MOUTH4
        sta cost
@e2:    ldx f
        lda feye,x
        ldy hidx
        cmp cureye,y
        beq @tail
        clc
        lda cost
        adc #EYE4
        sta cost

@tail:  ldx f                           ; want = fsound[f] - screen - cost
        txa
        asl
        tax
        sec
        lda fsound,x
        sbc screen
        sta want
        lda fsound+1,x
        sbc screen+1
        sta want+1
        bpl @pos
        lda #0                          ; already late: the carry catches up
        sta want
        sta want+1
        beq @units
@pos:   sec
        lda want
        sbc cost
        sta want
        lda want+1
        sbc #0
        sta want+1
        bpl @units
        lda #0
        sta want
        sta want+1

@units: lsr want+1                      ; quarter ms -> units of 2 ms
        ror want
        lsr want+1
        ror want
        lsr want+1
        ror want
        lda want+1
        beq @fits
        lda #255                        ; longer than one delay can hold
        sta want
        lda #0
        sta want+1
@fits:  lda want
        jsr delay2
        lda want                        ; screen += units * 8, in two halves
        lsr                             ; because the shifts that build the
        lsr                             ; low byte would clobber the carry
        lsr
        lsr
        lsr
        sta tmp2
        lda want
        asl
        asl
        asl
        clc
        adc screen
        sta screen
        lda tmp2
        adc screen+1
        sta screen+1

        lda KBD                         ; a key stops it between frames
        JPL @frame
        lda #$90                        ; and silences the card, which still
        sta SLOT4                       ; has most of the sentence queued
        bit KBDSTRB                     ; and is not also a character to type:
        lda #125                        ; a quarter second for the key to stop
        jsr delay2                      ; bouncing, then drop it again
        bit KBDSTRB
        rts

@done:  ldy hidx                        ; back to rest, eyes open
        lda #0
        sta curmouth,y
        sta cureye,y
        ldx #0
        jsr blit_mouth
        ldx #0
        jsr blit_eye
        jmp flip
