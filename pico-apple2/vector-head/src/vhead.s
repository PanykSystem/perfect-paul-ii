; ---------------------------------------------------------------------------
; The 1985 vector head, on the Apple II -- second cut.  ca65.
;
; The first cut drew the mouth with Bresenham every time it changed, in EOR, on
; the page being displayed.  Three things were wrong with that, and they were
; all the same thing: 585 mirrored pixels a shape, twice over to rub the old
; one out, is about 80 ms of 6502.  So
;
;   * you watched it happen -- the erase and the redraw straddled the raster;
;   * the animation ran at half speed;
;   * and worst, the 80 ms was spent BEFORE the allophone went to the card and
;     was not taken off the delay that followed, so the card ran dry between
;     allophones and the speech came out stretched and lagging.
;
; All three are fixed by not drawing at run time.  mkmouth_a2.py rasterises the
; ten shapes on the PC, composited over the face, and keeps each one as a
; 10 x 48 block of HGR bytes; a shape change is then a 480-byte block copy.
; Because the block carries the face with it, there is nothing to rub out, so
; the work halves again -- call it 7.8 ms against 160.
;
; That is under one frame, and it goes to the page that is not being displayed,
; so nothing is ever seen half drawn.  Page flipping is one soft switch.
;
; And the card is loaded up front.  Its stage holds 4096 allophones, which is
; about fifteen seconds, so the whole sentence goes across in one burst and the
; chip then speaks to its own clock with no gaps at all.  The animation follows
; the same duration table afterwards and cannot disturb it.
;
; The durations are measured out of the emulation itself, not read off the data
; sheet -- see mkscript2.py.  The data sheet is up to 45% long.
; ---------------------------------------------------------------------------

        .include "mouthdim_a2.inc"
        .include "jbranch.inc"
        .include "nrlzp.inc"
        .include "nrlsym.inc"

; The rule tables are a file of their own, BLOADed at $0C00, because this one
; already runs from $6000 to within a page of ProDOS.  The engine's buffers go
; below HGR page 1 for the same reason -- there is simply no room above.
NRLBUF  = $1A00
        .include "nrlbuf.inc"   ; equates only, so they can lead
strp    = $0A                   ; printing a message; plot's, but not at once

        .org $6000

; ---- zero page: only the pointers the block copy and the rasteriser use with
; ---- (zp),y.  Everything else lives above the program, where it costs nothing
; ---- that matters now that no line is drawn while the head is talking.
src     = $06                   ; block copy source
dst     = $08                   ; block copy destination
scr     = $0A                   ; plot: screen address of the current row
ptr     = $EB                   ; draw_list cursor

; ---- tables and scratch, parked clear of the program and of both HGR pages --
;
; TABLES has to clear the end of the program, and the program grows every time
; a shape is added: the eye group alone put 1.3 KB on it and ran the data
; straight under the tables at $8000, where hgr_init overwrote the allophones
; and half the bitmaps on its way past.  Nothing complained -- the head simply
; drew the wrong thing and spoke bytes that were never in the script.  So the
; assembler checks it now; see the .assert at the end of the file.
TABLES  = $9000

; Laid out end to end from their own sizes rather than at round addresses.
; Hand-picked offsets are how the eye's row table came to start five bytes
; short of div7 -- and because hgr_init builds div7 LAST, it wrote zeroes over
; the top of ehi, so the bottom five rows of every blink landed at $2000 and
; put a smear of eyelid across the top of the screen.
rowlo   = TABLES                ; 192
rowhi   = rowlo + 192           ; 192
mlo     = rowhi + 192           ; the mouth block's row addresses
mhi     = mlo + MOUTH_H
elo     = mhi + MOUTH_H         ; and the eye block's
ehi     = elo + EYE_H
div7    = ehi + EYE_H           ; 256
bitmask = div7 + 256            ; 256

SCRATCH = bitmask + 256
x0      = SCRATCH+0
y0      = SCRATCH+1
x1      = SCRATCH+2
y1      = SCRATCH+3
dxv     = SCRATCH+4
dyv     = SCRATCH+5
sxv     = SCRATCH+6
syv     = SCRATCH+7
err     = SCRATCH+8             ; 2
e2      = SCRATCH+10            ; 2
t       = SCRATCH+12            ; 2
tmp     = SCRATCH+14
tmpb    = SCRATCH+15
side    = SCRATCH+16
count   = SCRATCH+17
listbase= SCRATCH+18            ; 2
hidden  = SCRATCH+20            ; $00 or $20: the page NOT being displayed
hidx    = SCRATCH+21            ; the same thing as 0 or 1, to index by
frame   = SCRATCH+22
row     = SCRATCH+23
; What each PAGE is currently showing.  Not what the screen is showing: with
; two pages, a shape that is unchanged since the last frame is still two
; frames stale on the page about to be drawn into, so "has it changed" has to
; be asked of the page, not of the animation.
curmouth = SCRATCH+24           ; [2]
cureye  = SCRATCH+26            ; [2]

; run2.py pokes these to test one copy at a time; exporting them beats having
; the test hold its own opinion of where they live, which is what it did when
; TABLES moved and left it writing into the middle of the row table.
.export hidden, hidx, curmouth, cureye, TABLES
; run3.py reads the frame list and the allophones out of memory rather than
; recomputing them; exporting beats having the test hold its own opinion of
; where they live.
.export nf, fvis, feye, fsound, an, allo, work, linelen, msg_demo, getline, text_mirror, f, flip

KBD     = $C000
KBDSTRB = $C010
SLOT4   = $C0C0                 ; the card's write register, slot 4
MODEALLO = 177                  ; POKE SP,177 -- allophone mode
RAWBASE = $C0                   ; one raw allophone, no CR needed

TXTSET  = $C051
TXTCLR  = $C050
CLR80STORE = $C000              ; //e: write. See hgr_init.
CLR80VID   = $C00C
MIXSET  = $C053                 ; 280x160 and four lines of text
MIXCLR  = $C052
LOWSCR  = $C054                 ; display page 1
HISCR   = $C055                 ; display page 2
HIRES   = $C057

; Mixed mode, which is what this head was drawn for: it is 156 rows tall in a
; 160-row window, and the four text lines underneath are where the CPC put a
; text panel down the right.
;
; The catch is that PAGE2 moves the TEXT window to $0800 as well as moving the
; graphics to $4000, and $0800 is where the Applesoft loader that BRUN this
; lives.  But mixed mode only displays rows 20 to 23, which is $0A50 to $0BF7
; -- better than 300 bytes clear of a 252-byte loader and its handful of
; variables.  So the four lines are mirrored into the second text page and the
; loader is left alone.  Keep that loader small.
;
; The text window is set to those four rows as well, so COUT and GETLN scroll
; within them instead of up a screen nobody can see.
TXTWNDL = $20                   ; the monitor's text window
TXTWNDW = $21
TXTWNDT = $22
TXTWNDB = $23
TXTP1   = $0650                 ; row 20 of text page 1; rows 21-23 follow
TXTP2   = $0A50

; ===========================================================================
start:
        jsr nrl_init
        jsr set_window
        bit TXTSET
        bit LOWSCR
        jsr home
        lda #<msg_title
        ldy #>msg_title
        jsr puts
        ; Before anything can display page 2.  Its text half has never been
        ; written, and the head is drawn with page 2 up -- so without this the
        ; bottom four lines show whatever was in $0A50 for the second and a
        ; half that takes, and then again on every flip until the first thing
        ; is typed.
        jsr text_mirror

        jsr hgr_init            ; tables, soft switches, both pages cleared

        ; Build the face on page 1 while page 2 -- cleared -- is displayed, so
        ; it appears complete rather than drawing itself in front of you.
        bit HISCR
        lda #$00
        sta pageoff
        lda #<head_static
        ldy #>head_static
        jsr draw_list

        ; Each block covers only what MOVES, and every shape also carries
        ; fixed lines -- jaw, cheek, brow -- that reach outside its rectangle.
        ; Those are the same in every shape of the group, so drawing one of
        ; each here puts them on the page for good and the blocks then
        ; overwrite whatever of them falls inside.
        lda #<mouth_rest
        ldy #>mouth_rest
        jsr draw_list
        lda #<eye_open
        ldy #>eye_open
        jsr draw_list

        lda #$00                ; and the moving parts on top
        sta hidden
        sta hidx
        ldx #0
        jsr blit_mouth
        ldx #0
        jsr blit_eye

        bit LOWSCR              ; there it is, all at once
        jsr copy_page           ; page 2 gets the same, so either may be shown
        lda #0                  ; and both now hold rest / eyes open
        sta curmouth
        sta curmouth+1
        sta cureye
        sta cureye+1
        lda #$20
        sta hidden              ; page 2 is now the one we draw into
        lda #1
        sta hidx

        ; The demo sentence first, so it is still a demo, and then whatever
        ; is typed. The rules run here, not on the card: the card speaks what
        ; it is sent and cannot be asked what it made of it.
        lda #<msg_demo
        ldy #>msg_demo
        jsr set_work
        jmp speak

        ; The head stays on the screen from here on.  Mixed mode means the
        ; prompt and the face are up together, so there is no switching back
        ; to text and nothing to hold: it simply never goes away.
again:  jsr prompt
        lda linelen
        beq quit

speak:  jsr nrl_say
        jsr build_frames
        bit KBDSTRB             ; whatever the keyboard latched while typing
        jsr run_frames          ; is not a request to stop the sentence
        jmp again

quit:   lda #$90                ; in case anything is still queued
        sta SLOT4
        jsr full_window
        bit TXTSET
        bit LOWSCR              ; page 1, or BASIC prints into $0800
        jmp home

; ---------------------------------------------------------------------------
; The text side: one line in, through the monitor's own line editor so that
; backspace, escape and the cursor all behave the way the machine's owner
; expects rather than the way I would have reinvented them.
; ---------------------------------------------------------------------------
GETLN   = $FD6A
COUT    = $FDED
HOMETXT = $FC58
PROMPTC = $33
CH      = $24                   ; the monitor's cursor column
INBUF   = $0200

home:   jsr HOMETXT             ; and keep the second text page with it
        jmp text_mirror

set_window:                     ; COUT and GETLN get the bottom four rows
        lda #0
        sta TXTWNDL
        lda #40
        sta TXTWNDW
        lda #20
        sta TXTWNDT
        lda #24
        sta TXTWNDB
        rts

full_window:                    ; and the whole screen back on the way out
        lda #0
        sta TXTWNDT
        rts

; ---------------------------------------------------------------------------
; text_mirror -- the four visible rows into the second text page.
;
; PAGE2 moves the text window as well as the graphics, so without this the
; bottom four lines would change every time the animation flipped a page.
; ---------------------------------------------------------------------------
text_mirror:
        ldx #0
@row:   txa
        asl
        tay
        lda txt_rows,y
        sta src
        sta dst
        lda txt_rows+1,y
        sta src+1
        clc
        adc #$04                ; the second text page is $400 further on
        sta dst+1
        ldy #39
@byte:  lda (src),y
        sta (dst),y
        dey
        bpl @byte
        inx
        cpx #4
        bne @row
        rts

txt_rows:
        .addr TXTP1, TXTP1+$80, TXTP1+$100, TXTP1+$180

puts:   sta strp                ; A/Y = a NUL-terminated string
        sty strp+1
        ldy #0
@l:     lda (strp),y
        beq @d
        ora #$80                ; the Apple II wants the high bit set
        jsr COUT
        iny
        bne @l
@d:     rts

set_work:                       ; A/Y = a string -> work
        sta strp
        sty strp+1
        ldy #0
@l:     lda (strp),y
        sta work,y
        beq @d
        iny
        cpy #WORK_MAX
        bcc @l
        lda #0
        sta work,y
@d:     sty linelen
        rts

        ; Typing happens on page 1, so force it: the animation may have left
        ; page 2 up, and the echo goes to whichever text page is displayed.
; ---------------------------------------------------------------------------
; getline -- a line editor of our own, because the monitor's GETLN blocks and
; the head would sit there not blinking.
;
; It polls the keyboard on a 2 ms tick and spends the time between keystrokes
; running the blink.  Echoing goes to text page 1 whatever is displayed, so
; every change is mirrored to the second page before a flip can show the stale
; copy.
; ---------------------------------------------------------------------------
IDLE_HALF = 25                  ; 50 ms, in ticks
IDLE_SHUT = 40                  ; 80 ms
idle_gaps:
        .word 1150, 1850, 1450, 2150            ; 2.3 3.7 2.9 4.3 seconds

getline:
        lda #0
        sta linelen
        sta blink_ph
        sta idle_ct
        sta idle_ct+1
        lda #<1150
        sta blink_next
        lda #>1150
        sta blink_next+1
        lda #1
        sta blink_gi
        jsr cursor
@loop:  lda KBD
        bmi @key
        lda #1                  ; 2 ms, then one tick of the blink
        jsr delay2
        jsr idle_blink
        jmp @loop

@key:   bit KBDSTRB
        and #$7F
        cmp #13
        beq @done
        cmp #8
        beq @back
        cmp #127
        beq @back
        cmp #' '
        bcc @loop               ; no other control character is wanted
        ldx linelen
        cpx #WORK_MAX-1
        bcs @loop
        sta work,x
        inc linelen
        ora #$80
        jsr COUT
        jsr cursor
        jmp @loop

@back:  lda linelen
        beq @loop
        dec linelen
        jsr rubout
        jmp @loop

@done:  lda #' '+$80            ; take the cursor off the end of the line
        jsr COUT
        lda #13+$80
        jsr COUT
        ldy linelen
        lda #0                  ; the right context reads past the end
        sta work,y
        sta work+1,y
        sta work+2,y
        sta work+3,y
        jmp text_mirror

        ; At the right-hand edge the cursor would wrap to the next line and,
        ; on the window's last row, scroll it -- after which the backspace
        ; lands somewhere else entirely and leaves the underscore behind.
cursor: lda CH
        cmp #39
        bcs @skip
        lda #'_'+$80            ; show where the next character lands, then
        jsr COUT                ; step back so typing overwrites it
        lda #8+$80
        jsr COUT
@skip:  jmp text_mirror

rubout: lda #' '+$80            ; wipe the cursor, back up over the character
        jsr COUT
        lda #8+$80
        jsr COUT
        lda #8+$80
        jsr COUT
        jmp cursor

; ---------------------------------------------------------------------------
; idle_blink -- one 2 ms tick of the blink while the prompt waits.
;
; The animation blinks off the sentence's own clock, in build_frames; that one
; only runs while something is being said, so with the head now permanently on
; screen it sat there motionless between sentences.
; ---------------------------------------------------------------------------
idle_blink:
        inc idle_ct
        bne @test
        inc idle_ct+1
@test:  lda idle_ct+1
        cmp blink_next+1
        bcc @no
        bne @step
        lda idle_ct
        cmp blink_next
        bcs @step
@no:    rts
@step:  lda blink_ph
        beq @close1
        cmp #1
        beq @shut
        cmp #2
        beq @close2
        lda #0                  ; phase 3: open, and take the next gap
        sta blink_ph
        ldx #0
        jsr idle_eye
        lda blink_gi
        asl
        tax
        lda idle_gaps,x
        ldy idle_gaps+1,x
        jsr idle_at
        inc blink_gi
        lda blink_gi
        and #3
        sta blink_gi
        rts
@close1:
        ldx #1
        inc blink_ph
        jsr idle_eye
        lda #IDLE_HALF
        ldy #0
        jmp idle_at
@shut:  ldx #2
        inc blink_ph
        jsr idle_eye
        lda #IDLE_SHUT
        ldy #0
        jmp idle_at
@close2:
        ldx #1
        inc blink_ph
        jsr idle_eye
        lda #IDLE_HALF
        ldy #0
        jmp idle_at

idle_at:                        ; blink_next = idle_ct + A/Y
        clc
        adc idle_ct
        sta blink_next
        tya
        adc idle_ct+1
        sta blink_next+1
        rts

; X = eye shape, into the hidden page, then shown.  It copies even when that
; page already had the shape: keeping the two pages one phase apart costs 4 ms
; and saves reasoning about which of them is stale.
idle_eye:
        txa
        ldy hidx
        sta cureye,y
        tax
        jsr blit_eye
        jmp flip

prompt: bit LOWSCR
        lda #$20
        sta hidden
        lda #1
        sta hidx
        lda #<msg_ask
        ldy #>msg_ask
        jsr puts
        lda #'>'+$80
        jsr COUT
        jmp getline

msg_title:
        .byte "VECTOR HEAD -- SP0256 FIRMWARE, SLOT 4",13
        .byte "DRAWING THE HEAD...",13,0
msg_ask:
        .byte 13,"SAY WHAT? (RETURN ALONE TO STOP)",13,0
msg_demo:
        .byte "HELLO. I AM A VECTOR HEAD. ",0

; ---------------------------------------------------------------------------
; flip -- display the page just drawn, and draw into the other one next time.
; ---------------------------------------------------------------------------
flip:   lda hidden
        bne @two
        bit LOWSCR
        lda #$20
        sta hidden
        lda #1
        sta hidx
        rts
@two:   bit HISCR
        lda #$00
        sta hidden
        lda #0
        sta hidx
        rts

; ---------------------------------------------------------------------------
; blit_mouth -- X = shape, copied into the hidden page.
;
; Ten bytes a row unrolled: lda (src),y / sta (dst),y / iny is 13 cycles a byte
; against 16 for a dey/bpl loop, which over 480 bytes is 1.4 ms saved for 20
; bytes of code.
; ---------------------------------------------------------------------------
blit_mouth:
        txa
        asl                     ; two bytes per pointer
        tax
        lda mouth_ptr,x
        sta src
        lda mouth_ptr+1,x
        sta src+1
        lda #0
        sta row
@row:   ldx row
        lda mlo,x
        sta dst
        lda mhi,x
        clc
        adc hidden
        sta dst+1
        ldy #0
        .repeat MOUTH_W
        lda (src),y
        sta (dst),y
        iny
        .endrepeat
        clc
        lda src
        adc #MOUTH_W
        sta src
        bcc :+
        inc src+1
:       inc row
        lda row
        cmp #MOUTH_H
        bne @row
        rts

; ---------------------------------------------------------------------------
; blit_eye -- X = shape, into the hidden page.  As blit_mouth, 14 x 17.
; ---------------------------------------------------------------------------
blit_eye:
        txa
        asl
        tax
        lda eye_ptr,x
        sta src
        lda eye_ptr+1,x
        sta src+1
        lda #0
        sta row
@row:   ldx row
        lda elo,x
        sta dst
        lda ehi,x
        clc
        adc hidden
        sta dst+1
        ldy #0
        .repeat EYE_W
        lda (src),y
        sta (dst),y
        iny
        .endrepeat
        clc
        lda src
        adc #EYE_W
        sta src
        bcc :+
        inc src+1
:       inc row
        lda row
        cmp #EYE_H
        bne @row
        rts

; ---------------------------------------------------------------------------
; copy_page -- page 1 to page 2, all 8192 bytes.
; ---------------------------------------------------------------------------
copy_page:
        lda #$00
        sta src
        sta dst
        lda #$20
        sta src+1
        lda #$40
        sta dst+1
        ldx #32
@page:  ldy #0
@byte:  lda (src),y
        sta (dst),y
        iny
        bne @byte
        inc src+1
        inc dst+1
        dex
        bne @page
        rts

; ---------------------------------------------------------------------------
; delay2 -- wait A * 2 ms.
;
; 1.0205 MHz, so 2 ms is 2041 cycles.  The inner loop is 11 (2+2+2+2+3), its
; last pass 10 because the branch falls through, and the ldx/dey/bne around it
; another 7 -- so a unit is 11k + 6 and k = 185 makes that exactly 2041.
;
; The first draft used 186 and called it a quarter of a percent, having counted
; the inner loop and forgotten the outer.  The true figure was 2052, half a
; percent, and over the 1900-odd units of one sentence that is 21 ms of lag
; that no amount of staring at the arithmetic would have shown.  Measured by
; cal_delay.py, which is now the only thing that says what this costs.
; ---------------------------------------------------------------------------
delay2: tay
        beq @out
@unit:  ldx #185
@in:    nop
        nop
        nop
        dex
        bne @in
        dey
        bne @unit
@out:   rts

; ---------------------------------------------------------------------------
; hgr_init -- build the tables, switch the screen on, clear both pages.
;
; HGR's interleave is
;       $2000 + $400*(y&7) + $80*((y>>3)&7) + $28*(y>>6)
; and the middle term reaches 896, so it cannot be built in eight bits.  Done
; as a 16-bit composition instead, with k = (y>>3)&7:
;       hi = $20 + (y&7)*4 + (k>>1)
;       lo = (k&1)*$80 + 40*(y>>6)        (carrying into hi)
; Checks: y=8 -> $2080, y=16 -> $2100, y=64 -> $2028, y=191 -> $3FD0.
; ---------------------------------------------------------------------------
hgr_init:
        ldx #0
@row:   txa
        and #$07                ; (y & 7) * 4 into the high byte
        asl
        asl
        clc
        adc #$20
        sta tmpb
        txa
        lsr
        lsr
        lsr
        and #$07                ; k = (y>>3) & 7
        sta tmp
        lsr                     ; k >> 1 adds to hi
        clc
        adc tmpb
        sta rowhi,x
        lda tmp
        and #$01                ; k & 1 contributes $80 to lo
        beq @nohalf
        lda #$80
@nohalf:
        sta tmpb
        txa
        lsr                     ; y >> 6, i.e. 0..2
        lsr
        lsr
        lsr
        lsr
        lsr
        tay
        lda tmpb
@mul40: cpy #0
        beq @lodone
        clc
        adc #40
        bcc @nocarry
        inc rowhi,x
@nocarry:
        dey
        jmp @mul40
@lodone:
        sta rowlo,x
        inx
        cpx #192
        bne @row

        ; The mouth block's own row addresses, left column included, so the
        ; copy adds nothing per row but the page.
        ldx #0
@mrow:  txa
        clc
        adc #MOUTH_ROW0
        tay
        lda rowlo,y
        clc
        adc #MOUTH_COL
        sta mlo,x
        lda rowhi,y
        adc #0
        sta mhi,x
        inx
        cpx #MOUTH_H
        bne @mrow

        ldx #0
@erow:  txa
        clc
        adc #EYE_ROW0
        tay
        lda rowlo,y
        clc
        adc #EYE_COL
        sta elo,x
        lda rowhi,y
        adc #0
        sta ehi,x
        inx
        cpx #EYE_H
        bne @erow

        ; div7 and bitmask: seven pixels to a byte, bit 7 left alone so the
        ; display stays monochrome and a pixel cannot disturb its neighbours.
        ldx #0
        ldy #0
        lda #$01
@col:   sta bitmask,x
        pha
        tya
        sta div7,x
        pla
        asl
        cmp #$80                ; past the seventh bit?
        bne @same
        iny
        lda #$01
@same:  inx
        bne @col

        ; On a //e with 80STORE set, $C055 selects auxiliary memory instead of
        ; display page 2 -- so the flip would swap the language card in under
        ; the program rather than showing the other page.  BASIC.SYSTEM leaves
        ; 80STORE set if the 80-column firmware was ever switched on, and
        ; nothing here would survive it.  Both writes are harmless on a II+,
        ; where $C000 is the keyboard and ignores writes.
        sta CLR80STORE
        sta CLR80VID

        bit TXTCLR
        bit HIRES
        bit MIXSET
        bit LOWSCR

hgr_clear:                      ; both pages: $2000 through $5FFF
        lda #$00
        sta scr
        lda #$20
        sta scr+1
        ldx #64
        lda #0
@page:  ldy #0
@byte:  sta (scr),y
        iny
        bne @byte
        inc scr+1
        dex
        bne @page
        rts

; ---------------------------------------------------------------------------
; plot -- one pixel.  X = x (0..255), Y = row (0..191).  Only the face uses
; this now, once, so pageoff costs nothing worth counting.
; ---------------------------------------------------------------------------
plot:
        lda rowlo,y
        sta scr
        lda rowhi,y
        clc
        adc pageoff
        sta scr+1
        txa
        tay                     ; index the column tables by x
        lda div7,y
        sta tmp
        lda bitmask,y
        ldy tmp
        ora (scr),y             ; OR, never EOR -- see below
        sta (scr),y
        rts

; The first cut EORed the moving shapes, because that is what the CPC does and
; EOR is how you rub something out without keeping a copy of what was under it.
; Nothing here is ever rubbed out -- the block copy brings the face with it --
; so the only thing EOR still did was cancel 26 to 44 face pixels where a shape
; crossed the mesh, a DIFFERENT set for each shape, which reads as dust
; crawling over the face while it talks.

; ---------------------------------------------------------------------------
; line -- (x0,y0) to (x1,y1).  Bresenham, all eight octants.
; ---------------------------------------------------------------------------
line:
        sec                     ; dxv = |x1-x0|, sxv = step
        lda x1
        sbc x0
        bcs @xpos
        eor #$FF
        clc
        adc #1
        ldy #$FF
        bne @xset
@xpos:  ldy #$01
@xset:  sta dxv
        sty sxv

        sec                     ; dyv = |y1-y0|, syv = step
        lda y1
        sbc y0
        bcs @ypos
        eor #$FF
        clc
        adc #1
        ldy #$FF
        bne @yset
@ypos:  ldy #$01
@yset:  sta dyv
        sty syv

        sec                     ; err = dxv - dyv, signed 16-bit
        lda dxv
        sbc dyv
        sta err
        lda #0
        sbc #0
        sta err+1

@loop:  ldx x0
        ldy y0
        jsr plot

        lda x0
        cmp x1
        bne @step
        lda y0
        cmp y1
        beq @done

        ; e2 is taken ONCE and both tests use it.  Computing it again after the
        ; x step -- which is what the first draft did -- lets the walk diverge
        ; and never reach the end point.
        ;     if e2 > -dy : err -= dy ; x += sx
        ;     if e2 <  dx : err += dx ; y += sy
        ; Both are sign tests rather than signed 16-bit comparisons:
        ;     e2 > -dy  <=>  e2 + dy > 0
        ;     e2 <  dx  <=>  e2 - dx < 0
@step:  lda err                 ; e2 = 2 * err
        asl
        sta e2
        lda err+1
        rol
        sta e2+1

        clc                     ; t = e2 + dy
        lda e2
        adc dyv
        sta t
        lda e2+1
        adc #0
        sta t+1
        bmi @noxstep
        lda t
        ora t+1
        beq @noxstep            ; e2 = -dy exactly: no step
        jsr @xstep
@noxstep:
        sec                     ; t = e2 - dx
        lda e2
        sbc dxv
        sta t
        lda e2+1
        sbc #0
        sta t+1
        bpl @loop
        clc                     ; err += dx ; y += sy
        lda err
        adc dxv
        sta err
        lda err+1
        adc #0
        sta err+1
        clc
        lda y0
        adc syv
        sta y0
        jmp @loop
@done:  rts

@xstep: sec                     ; err -= dyv
        lda err
        sbc dyv
        sta err
        lda err+1
        sbc #0
        sta err+1
        clc                     ; x0 += sxv
        lda x0
        adc sxv
        sta x0
        rts

; ---------------------------------------------------------------------------
; draw_list -- a polyline list, both halves.
;       .byte N, (dx,row) * N, ... , 0
; A/Y = address of the list.
; ---------------------------------------------------------------------------
draw_list:
        sta listbase            ; the list is walked twice, so keep the start
        sty listbase+1
        lda #0
        sta side
@pass:  lda listbase
        sta ptr
        lda listbase+1
        sta ptr+1
@poly:  jsr getb                ; N, or 0 to end
        beq @nextside
        sta count
        jsr getpt               ; the first point is the cursor
        sta x0
        stx y0
        dec count
@seg:   jsr getpt
        sta x1
        stx y1
        lda x1
        pha                     ; line() walks x0/y0, so keep the end point
        lda y1
        pha
        jsr line
        pla
        sta y0
        pla
        sta x0
        dec count
        bne @seg
        jmp @poly
@nextside:
        inc side
        lda side
        cmp #2
        bcc @pass
        rts

; ---------------------------------------------------------------------------
; getb -- one byte from the list, advancing a 16-bit cursor.
;
; head_static is 387 bytes, so an 8-bit index is not enough: it wraps at 256
; and the walk restarts in the middle of the data and never ends.
; ---------------------------------------------------------------------------
getb:   ldy #0
        lda (ptr),y
        inc ptr
        bne :+
        inc ptr+1
:       ora #0                  ; the INCs clobbered Z; the caller tests the
        rts                     ; BYTE for the terminator, not the pointer

; one (dx,row) pair -> A = x, X = row
getpt:  jsr getb
        sta tmp
        jsr getb
        tax                     ; X = row
        lda side
        bne @right
        lda #HEAD_CX            ; left half:  x = CX - dx
        sec
        sbc tmp
        rts
@right: lda tmp                 ; right half: x = CX + dx
        clc
        adc #HEAD_CX
        rts

pageoff: .byte 0                ; $00 page 1, $20 page 2 -- for plot only

        .include "anim.inc"
        .include "nrl.inc"
        .include "durdata.inc"
        .include "headdata_a2.inc"
        .include "mouthdata_a2.inc"

mouth_ptr:
        .repeat NVISEME, i
        .addr mouth_bits + i * MOUTH_SIZE
        .endrepeat
eye_ptr:
        .repeat NEYE, i
        .addr eye_bits + i * EYE_SIZE
        .endrepeat

; The program must end below the tables.  It is 1.3 KB bigger than it was when
; TABLES was chosen, and the next shape added would have walked into them again
; -- silently, because a table being built over data looks like nothing at all
; until the head draws the wrong face and speaks bytes that were never in the
; script.
.assert * <= TABLES, error, "the program has grown into the tables at TABLES"
.assert SCRATCH + 28 <= $9500, error, "the tables have run into ProDOS"
