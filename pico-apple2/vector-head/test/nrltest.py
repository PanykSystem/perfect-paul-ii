"""Check the 6502 rules against the firmware's, word for word.

There are now two implementations of the same rules -- nrl.c on the card and
nrl.inc on the Apple II -- and the only thing that keeps two implementations
honest is running both.  The tables come out of nrl.c, so what this really
tests is the 6502 matcher: the context classes, the backwards left-context
walk, the exception splice and all of stage 2's positional variants.

A mismatch here is not cosmetic.  The card speaks what nrl.c decides; if the
6502 decides anything else, the mouth animates a different sentence from the
one being spoken, and the drift is silent.
"""
import subprocess, sys
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

NRL = '../../sp0256/host/nrl_test'      # build it with sp0256/host/Makefile

sym = {}
for ln in open('nrltest.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)

code = open('nrltest.bin', 'rb').read()
data = open('../src/nrldata.bin', 'rb').read()
NRL_ORG = int(next(l.split('=')[1].strip().lstrip('$')
                   for l in open('../src/nrlsym.inc') if l.startswith('NRL_ORG')), 16)
names = [l.split()[0][3:] for l in open('../tools/allophones.txt') if l.startswith('SP_')]
NAME = {i: n for i, n in enumerate(names)}


def run6502(text):
    mem = ObservableMemory()
    mpu = MPU(memory=mem)
    for i, b in enumerate(code):
        mem[0x6000 + i] = b
    for i, b in enumerate(data):
        mem[NRL_ORG + i] = b
    w = sym['work']
    t = text.upper().encode()
    assert len(t) <= 120, text
    for i, b in enumerate(t):
        mem[w + i] = b
    for i in range(len(t), len(t) + 8):
        mem[w + i] = 0
    mpu.pc = sym['start']
    mpu.sp = 0xFD
    n = 0
    while n < 8_000_000:
        mpu.step(); n += 1
        if mpu.sp > 0xFD:
            break
    else:
        raise SystemExit('6502 did not return on %r' % text)
    an = mem[sym['an']]
    return [mem[sym['allo'] + i] for i in range(an)], n


def runc(text):
    out = subprocess.run([NRL, text], capture_output=True, text=True).stdout
    line = next(l for l in out.splitlines() if 'al2 :' in l)
    toks = line.split('al2 :')[1].split()
    ids = {n: i for i, n in enumerate(names)}
    return [ids[t] for t in toks if t in ids]


words = sys.argv[1:]
if not words:
    words = """HELLO WORLD THE QUICK BROWN FOX JUMPS OVER A LAZY DOG
    APPLE COMPUTER VECTOR HEAD SPEAKING MACHINE DIGIT BUSY WOMEN ENOUGH LAUGH
    MICHAEL SCHNEIDER FRIEND HEART SAYS LIVE HI HIYA HEY OH BYE GOODBYE
    ABOUT YOUR VERY WANT PROBLEM ONCE WHERE PEOPLE AGAIN DIGITAL DIGITIZE
    HEAD BROUGHT SAID DOES MOTHER WHO GREAT BUILD THOUGHT THROUGH BROWN
    NATION MOTION QUESTION SPECIAL OCEAN PLEASURE MEASURE TREASURE
    CHURCH CHAIR SCHOOL CHORUS CHEF MACHINE PSYCHOLOGY RHYTHM
    SKY CLEAR COMB CAN'T GUEST GOT WIG PART COULD DO SADDLE LAKE BRAIN RURAL
    THEY BATHE THIN NO HE HOE FIR LETTER FOOD TO SORRY MERRY MARRY
    ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE TWENTY
    HUNDRED THOUSAND MILLION ZERO FIRST SECOND THIRD
    EXCELLENT WONDERFUL TERRIBLE BEAUTIFUL IMPOSSIBLE UNDERSTANDING
    PHOTOGRAPH PHOTOGRAPHY TELEPHONE MICROPHONE XYLOPHONE
    KNIGHT KNOW GNOME WRITE WRONG LAMB THUMB DEBT ISLAND
    EYES EARS NOSE MOUTH FACE SMILE TALK LISTEN WATCH
    ACTION FRACTION FRICTION SECTION STATION VACATION
    SINGING RINGING BRINGING WALKING TALKING RUNNING
    LOVELY LONELY FRIENDLY QUICKLY SLOWLY BADLY
    USE USED USING MUSIC MUSICAL AMUSE CONFUSE REFUSE
    TUNE DUNE JUNE LUNE PRUNE BLUE TRUE GLUE CLUE
    CITY CYCLE CYNIC CELL CENT CIRCLE JUICE JUDGE
    """.split()

bad = 0
cycles = 0
for w in words:
    got, n = run6502(w)
    cycles += n
    exp = runc(w)
    if got != exp:
        bad += 1
        if bad <= 12:
            print('%-14s 6502: %s' % (w, ' '.join(NAME[c] for c in got)))
            print('%-14s   C : %s' % ('', ' '.join(NAME[c] for c in exp)))
print('\n%d words, %d mismatches  (%.0f k instructions, %.0f per word)'
      % (len(words), bad, cycles / 1000.0, cycles / len(words)))
sys.exit(1 if bad else 0)
