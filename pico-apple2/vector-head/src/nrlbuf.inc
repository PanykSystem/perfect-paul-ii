; ---------------------------------------------------------------------------
; Working storage for the NRL engine, laid out from NRLBUF, which the includer
; defines.  Equates rather than .res so the head's binary does not carry two
; kilobytes of zeroes to disk, and sized from each other so nothing can be
; hand-placed into its neighbour -- which is how the eye row table came to
; overlap div7.
; ---------------------------------------------------------------------------
WORK_MAX = 120                  ; the left matcher walks X below zero and tests
                                ; bit 7, so this must stay under 128
PH_MAX   = 160
ALLO_MAX = 160

wi       = NRLBUF + 0
wlen     = NRLBUF + 1
saidlen  = NRLBUF + 2
lenL     = NRLBUF + 3
lenM     = NRLBUF + 4
lenR     = NRLBUF + 5
lenO     = NRLBUF + 6
moff     = NRLBUF + 7
roff     = NRLBUF + 8
ooff     = NRLBUF + 9
pidx     = NRLBUF + 10
pend     = NRLBUF + 11
pn       = NRLBUF + 12
an       = NRLBUF + 13
i2       = NRLBUF + 14
gw       = NRLBUF + 15
cur      = NRLBUF + 16
prev     = NRLBUF + 17
nextp    = NRLBUF + 18
tmp1     = NRLBUF + 19
tmp2     = NRLBUF + 20

work     = NRLBUF + 48          ; the right context reads up to two characters
tail     = work + WORK_MAX + 8  ; past the end, so each buffer is padded
ph       = tail + WORK_MAX + 8
allo     = ph + PH_MAX
cls256   = allo + ALLO_MAX
NRLBUF_END = cls256 + 256

; The frame list, built from the allophones at run time.
FRAME_MAX = 128
fvis     = NRLBUF_END
feye     = fvis + FRAME_MAX
fsound   = feye + FRAME_MAX     ; 16-bit, and one past the end holds the finish
FRAMEBUF_END = fsound + 2 * (FRAME_MAX + 1)

; Everything the frame builder and the animator count with.
nf       = NRLBUF + 21
k        = NRLBUF + 22
f        = NRLBUF + 23
lastv    = NRLBUF + 24
laste    = NRLBUF + 25
vnow     = NRLBUF + 26
eyenow   = NRLBUF + 27
blink_ph = NRLBUF + 28
blink_gi = NRLBUF + 29
blink_at = NRLBUF + 30          ; 2
sound    = NRLBUF + 32          ; 2
screen   = NRLBUF + 34          ; 2
cost     = NRLBUF + 36
want     = NRLBUF + 37          ; 2
linelen  = NRLBUF + 39
idle_ct  = NRLBUF + 40          ; 2, in 2 ms ticks while the prompt waits
blink_next = NRLBUF + 42        ; 2
