; Zero page for the NRL engine, which has to be in scope before the code that
; uses it or ca65 assumes absolute addressing and the matchers get slower for
; no reason.
rp      = $06                   ; rule cursor      (blits use these, but never
fixp    = $08                   ; exception cursor  while the rules are running)

