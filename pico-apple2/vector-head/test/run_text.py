"""Is the second text page ever displayed holding something nobody wrote?

The head is built with page 2 up, and PAGE2 moves the text window to $0800 as
well as the graphics -- so the bottom four lines come from $0A50, which nothing
had written.  They showed a second and a half of whatever was in RAM, and then
again on every flip until the first thing was typed.

So: fill both text pages with a known pattern first, then check at every
moment page 2 becomes the displayed page that its four visible rows match
page 1's.  If they do, nothing uninitialised can be on screen.
"""
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

sym = {}
for ln in open('../src/vhead.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)

ROWS = [0x0650, 0x06D0, 0x0750, 0x07D0]         # text rows 20..23, page 1
mem = ObservableMemory(); mpu = MPU(memory=mem)
bad, shows = [], [0]
keys = []


def kbd(addr):
    if addr == 0xC000:
        return (0x80 | keys[0]) if keys else 0
    if addr == 0xC010 and keys:
        keys.pop(0)
    return 0


def check():
    for r in ROWS:
        for i in range(40):
            if mem[r + i] != mem[r + 0x400 + i]:
                return False
    return True


def soft(addr, value=None):
    if addr in (0xC000, 0xC010):
        return kbd(addr)
    if addr == 0xC055:                          # page 2 is now displayed
        shows[0] += 1
        if not check():
            bad.append((shows[0], mpu.processorCycles))
    return 0


for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
          0xC057, 0xC010):
    mem.subscribe_to_write([a], lambda addr, value: soft(addr))
    mem.subscribe_to_read([a], soft)
mem.subscribe_to_write([0xC0C0], lambda addr, value: None)

for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
    mem[0x6000 + i] = b
for i, b in enumerate(open('../src/nrldata.bin', 'rb').read()):
    mem[0x0C00 + i] = b
for a in (0xFDED, 0xFC58):                      # COUT and HOME do nothing, so
    mem[a] = 0x60                               # only text_mirror can match them
mem[sym['delay2']] = 0x60
import os
if os.environ.get('BREAK_MIRROR'):
    mem[sym['text_mirror']] = 0x60              # prove the test can fail

for i in range(0x0400, 0x0C00):                 # neither page is blank to start
    mem[i] = 0xDD if i < 0x0800 else 0xEE

pending = ["HELLO THERE", ""]
mpu.pc = sym['start']; mpu.sp = 0xFF
n = 0
while n < 20_000_000:
    if mpu.pc == sym['getline'] and not keys and pending:
        keys.extend([ord(c) for c in pending.pop(0)] + [13])
    mpu.step(); n += 1
    if not pending and mpu.pc == sym['quit']:
        break

print('page 2 displayed %d times' % shows[0])
print('times its four visible rows did not match page 1: %d' % len(bad))
for b in bad[:5]:
    print('  show #%d' % b[0])
