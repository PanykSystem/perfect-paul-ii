; ca65 here has no long branches, and the cmp chains below reach past 127
; bytes.  These expand to a short branch over a jmp only where that is needed;
; the plain b-forms are left alone everywhere they still reach.
.macro JEQ t
        bne :+
        jmp t
:
.endmacro
.macro JNE t
        beq :+
        jmp t
:
.endmacro
.macro JCS t
        bcc :+
        jmp t
:
.endmacro
.macro JCC t
        bcs :+
        jmp t
:
.endmacro

.macro JPL t
        bmi :+
        jmp t
:
.endmacro
.macro JMI t
        bpl :+
        jmp t
:
.endmacro
