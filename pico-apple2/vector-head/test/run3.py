"""The whole thing: type a sentence, and check what is spoken and what is drawn.

The head now works the allophones out for itself, so there are three places it
can go wrong that the canned-script version did not have: the rules, the frame
list built from them, and the delays computed from that.  All three are checked
here against the firmware's own answer for the same text.
"""
import subprocess, sys, io, contextlib, importlib.util, os
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

NRL = '../../sp0256/host/nrl_test'      # build it with sp0256/host/Makefile
CLK = 1020484.0

sym = {}
for ln in open('../src/vhead.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)
names = [l.split()[0][3:] for l in open('../tools/allophones.txt') if l.startswith('SP_')]
ids = {n: i for i, n in enumerate(names)}

spec = importlib.util.spec_from_file_location('mkm', '../tools/mkmouth_a2.py')
mkm = importlib.util.module_from_spec(spec)
here = os.getcwd(); os.chdir('..')
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(mkm)
os.chdir(here)

COUT, HOMETXT = 0xFDED, 0xFC58

# The head reads the keyboard itself now -- the monitor's GETLN blocks and the
# blink needs the time between keystrokes -- so the harness has to behave like
# a keyboard: $C000 holds the latched key, $C010 takes it.
keys = []


def kbd(addr):
    if addr == 0xC000:
        return (0x80 | keys[0]) if keys else 0
    if addr == 0xC010 and keys:
        keys.pop(0)
    return 0


def session(lines, realdelay=False, check_frames=False):
    mem = ObservableMemory()
    mpu = MPU(memory=mem)
    card, flips, shown = [], [], [1]

    def soft(addr, value=None):
        if addr in (0xC000, 0xC010):
            return kbd(addr)
        if addr == 0xC054:
            shown[0] = 1; flips.append(mpu.processorCycles)
        elif addr == 0xC055:
            shown[0] = 2; flips.append(mpu.processorCycles)
        return 0

    for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
              0xC057, 0xC010):
        mem.subscribe_to_write([a], lambda addr, value: soft(addr))
        mem.subscribe_to_read([a], soft)
    mem.subscribe_to_write([0xC0C0],
                           lambda addr, value: card.append((value, mpu.processorCycles)))

    for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
        mem[0x6000 + i] = b
    for i, b in enumerate(open('../src/nrldata.bin', 'rb').read()):
        mem[0x0C00 + i] = b
    if not realdelay:
        mem[sym['delay2']] = 0x60                    # RTS
    for a in (COUT, HOMETXT):
        mem[a] = 0x60

    keys.clear()
    pending = list(lines)
    mpu.pc = sym['start']; mpu.sp = 0xFF
    n = 0
    frames = []
    while n < 60_000_000:
        if mpu.pc == sym['getline'] and not keys and pending:
            keys.extend([ord(c) for c in pending.pop(0)] + [13])
        before = len(flips)
        mpu.step(); n += 1
        if check_frames and len(flips) > before and card:
            frames.append((shown[0], mpu.processorCycles))
        if mpu.sp > 0xFF - 1 and mpu.pc not in (sym['start'],) and n > 10:
            if mem[mpu.pc] == 0x00:
                break
        if not pending and len(card) and mpu.pc == sym['quit']:
            break
    return mem, card, flips, frames, n


def expect(text):
    out = subprocess.run([NRL, text], capture_output=True, text=True).stdout
    toks = next(l for l in out.splitlines() if 'al2 :' in l).split('al2 :')[1].split()
    return [ids[t] for t in toks if t in ids]


TEXTS = ["HELLO. I AM A VECTOR HEAD. ",
         "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG",
         "WHAT DO YOU WANT TO TALK ABOUT",
         "MICHAEL'S APPLE TWO E HAS 2 CARDS"]

mem, card, flips, _, n = session(TEXTS[1:], check_frames=False)
print('simulated %d instructions for %d sentences' % (n, len(TEXTS)))

got = [b for b, _ in card]
runs, cur = [], []
for b in got:
    if b == 177:
        if cur:
            runs.append(cur)
        cur = []
    else:
        cur.append(b & 0x3F)
if cur:
    runs.append(cur)

print('\nsentences spoken: %d' % len(runs))
bad = 0
for text, allo in zip(TEXTS, runs):
    exp = expect(text)
    ok = (allo == exp)
    bad += not ok
    print('  %-44s %3d allophones  %s' % ('"%s"' % text[:42], len(allo),
                                          'match' if ok else 'MISMATCH'))
    if not ok:
        print('     6502: %s' % ' '.join(names[c] for c in allo))
        print('       C : %s' % ' '.join(names[c] for c in exp))
print('\nmismatches against the firmware: %d' % bad)


# ---- what is on the screen, frame by frame --------------------------------
def hgr(mem, base):
    px = [[0] * 280 for _ in range(192)]
    for y in range(192):
        a = base + 0x400 * (y & 7) + 0x80 * ((y >> 3) & 7) + 40 * (y >> 6)
        for b in range(40):
            v = mem[a + b]
            for bit in range(7):
                if v & (1 << bit):
                    px[y][b * 7 + bit] = 1
    return px


def want_px(v, e):
    return [[m | y for m, y in zip(rm, re)]
            for rm, re in zip(mkm.shapes[v], mkm.eyes[e])]


ONE = ["THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"]
mem = ObservableMemory(); mpu = MPU(memory=mem)
card, flips, shown, checked, wrong = [], [], [1], [], []


def soft2(addr, value=None):
    if addr in (0xC000, 0xC010):
        return kbd(addr)
    if addr == 0xC054:
        shown[0] = 1; flips.append(mpu.processorCycles)
    elif addr == 0xC055:
        shown[0] = 2; flips.append(mpu.processorCycles)
    return 0


for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
          0xC057, 0xC010):
    mem.subscribe_to_write([a], lambda addr, value: soft2(addr))
    mem.subscribe_to_read([a], soft2)
mem.subscribe_to_write([0xC0C0],
                       lambda addr, value: card.append((value, mpu.processorCycles)))
for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
    mem[0x6000 + i] = b
for i, b in enumerate(open('../src/nrldata.bin', 'rb').read()):
    mem[0x0C00 + i] = b
for a in (COUT, HOMETXT):
    mem[a] = 0x60
# Blank the demo sentence rather than jumping past it: the head is drawn on
# the way there, and skipping that leaves both pages empty -- which looks
# exactly like every frame being wrong.
mem[sym['msg_demo']] = 0

pending = list(ONE)
mpu.pc = sym['start']; mpu.sp = 0xFF
n, seen, t0 = 0, 0, None
while n < 40_000_000:
    if mpu.pc == sym['getline'] and not keys and pending:
        keys.extend([ord(c) for c in pending.pop(0)] + [13])
    before = len(flips)
    mpu.step(); n += 1
    # The blanked demo still runs a frame of its own, so only start checking
    # once the TYPED sentence has been handed to the card -- its mode byte is
    # the second 177 to go across.
    if len(flips) > before and sum(1 for b, _ in card if b == 177) >= 2:
        if t0 is None:
            t0 = card[-1][1]
        nf = mem[sym['nf']]
        if seen < nf:
            v = mem[sym['fvis'] + seen]
            e = mem[sym['feye'] + seen]
            page = hgr(mem, 0x2000 if shown[0] == 1 else 0x4000)
            ref = want_px(v, e)
            d = sum(1 for y in range(192) for x in range(280)
                    if page[y][x] != ref[y][x])
            checked.append((seen, v, e, flips[-1]))
            if d:
                wrong.append((seen, v, e, d))
        seen += 1
    if not pending and mpu.pc == sym['quit']:
        break

nf = mem[sym['nf']]
print('\nframes: %d built, %d displayed and checked' % (nf, len(checked)))
print('frames showing the wrong thing: %d' % len(wrong))
for w in wrong[:6]:
    print('  frame %d wanted mouth %d eye %d: %d pixels differ' % w)
blinks = [c for c in checked if c[2] == 2]
print('blinks in this sentence: %d' % len(blinks))
