"""Screenshots, taken off the real binary running on a simulated 6502.

The graphics half is the actual HGR framebuffer, decoded through the display's
own interleave -- the same decode the tests compare against the rasteriser, so
what is in these pictures is what the Apple II puts on the screen.  The text
half is rendered with a monospace font rather than the Apple II character ROM,
which is not here; the words and their positions are real, the letterforms are
not.
"""
import io, os, contextlib, importlib.util, sys
from PIL import Image, ImageDraw, ImageFont
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
SX, SY = 2, 2                                   # HGR pixels are not square;
                                                # 2x both ways keeps it simple
sym = {}
for ln in open('vh2.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)

spec = importlib.util.spec_from_file_location('mkm', 'mkmouth_a2.py')
mkm = importlib.util.module_from_spec(spec)
here = os.getcwd(); os.chdir('..')
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(mkm)
os.chdir(here)

mem = ObservableMemory(); mpu = MPU(memory=mem)
keys, flips, shown = [], [], [1]


def kbd(addr):
    if addr == 0xC000:
        return (0x80 | keys[0]) if keys else 0
    if addr == 0xC010 and keys:
        keys.pop(0)
    return 0


def soft(addr, value=None):
    if addr in (0xC000, 0xC010):
        return kbd(addr)
    if addr == 0xC054:
        shown[0] = 1; flips.append(1)
    elif addr == 0xC055:
        shown[0] = 2; flips.append(2)
    return 0


for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
          0xC057, 0xC010):
    mem.subscribe_to_write([a], lambda addr, value: soft(addr))
    mem.subscribe_to_read([a], soft)
mem.subscribe_to_write([0xC0C0], lambda addr, value: None)
for i, b in enumerate(open('vh2.bin', 'rb').read()):
    mem[0x6000 + i] = b
for i, b in enumerate(open('nrldata.bin', 'rb').read()):
    mem[0x0C00 + i] = b
mem[sym['delay2']] = 0x60

TROW = [0x0400 + 0x80 * (r & 7) + 40 * (r >> 3) for r in range(24)]


def cout(a):
    """$FDED, enough of it: the window, the wrap and the scroll."""
    ch, cv = mem[0x24], mem[0x25]
    top, bot, wid = mem[0x22], mem[0x23], mem[0x21]
    c = a & 0x7F
    if c == 13:
        ch, cv = 0, cv + 1
    elif c == 8:
        # The monitor's backspace steps back over a line break; getting this
        # wrong here leaves stray cursors in the pictures that the Apple II
        # would never show.
        if ch > 0:
            ch -= 1
        elif cv > top:
            ch, cv = wid - 1, cv - 1
    else:
        mem[TROW[cv] + ch] = a
        ch += 1
        if ch >= wid:
            ch, cv = 0, cv + 1
    if cv >= bot:
        for r in range(top, bot - 1):
            for i in range(wid):
                mem[TROW[r] + i] = mem[TROW[r + 1] + i]
        for i in range(wid):
            mem[TROW[bot - 1] + i] = 0xA0
        cv = bot - 1
    mem[0x24], mem[0x25] = ch, cv


def hometxt():
    top, bot, wid = mem[0x22], mem[0x23], mem[0x21]
    for r in range(top, bot):
        for i in range(wid):
            mem[TROW[r] + i] = 0xA0
    mem[0x24], mem[0x25] = 0, top


def hgr(base):
    px = [[0] * 280 for _ in range(192)]
    for y in range(192):
        a = base + 0x400 * (y & 7) + 0x80 * ((y >> 3) & 7) + 40 * (y >> 6)
        for b in range(40):
            v = mem[a + b]
            for bit in range(7):
                if v & (1 << bit):
                    px[y][b * 7 + bit] = 1
    return px


font = ImageFont.truetype(FONT, 13)


def shot(path, rows=160, text=True, caption_rows=(20, 21, 22, 23)):
    """The displayed page, graphics and -- in mixed mode -- the text under it."""
    h = 192 if text else rows
    im = Image.new('RGB', (280 * SX, h * SY), (0, 0, 0))
    px = hgr(0x2000 if shown[0] == 1 else 0x4000)
    d = ImageDraw.Draw(im)
    for y in range(min(rows, h)):
        for x in range(280):
            if px[y][x]:
                d.rectangle([x * SX, y * SY, x * SX + SX - 1, y * SY + SY - 1],
                            fill=(255, 255, 255))
    if text:
        base = 0x400 if shown[0] == 1 else 0x800
        for i, r in enumerate(caption_rows):
            addr = base + (TROW[r] - 0x400)
            line = ''.join(chr(mem[addr + c] & 0x7F) for c in range(40))
            for c, ch in enumerate(line):
                if ch not in ' \x00':
                    d.text((c * 7 * SX + 1, (160 + i * 8) * SY), ch,
                           font=font, fill=(255, 255, 255))
    im.save(path)
    return im


# ---- run it, grabbing pictures on the way ---------------------------------
SENTENCE = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
pending = [SENTENCE]
mpu.pc = sym['start']; mpu.sp = 0xFF
n, grabbed, gif_frames = 0, {}, []
while n < 20_000_000:
    if mpu.pc == 0xFDED:
        cout(mpu.a)
        mpu.pc = (mem[0x0100 + ((mpu.sp + 1) & 0xFF)]
                  | (mem[0x0100 + ((mpu.sp + 2) & 0xFF)] << 8)) + 1
        mpu.sp = (mpu.sp + 2) & 0xFF
        continue
    if mpu.pc == 0xFC58:
        hometxt()
        mpu.pc = (mem[0x0100 + ((mpu.sp + 1) & 0xFF)]
                  | (mem[0x0100 + ((mpu.sp + 2) & 0xFF)] << 8)) + 1
        mpu.sp = (mpu.sp + 2) & 0xFF
        continue
    if mpu.pc == sym['getline'] and not keys and pending:
        keys.extend([ord(c) for c in pending.pop(0)] + [13])
    mpu.step(); n += 1
    # Mid-sentence, on a wide-open mouth, with the typed line still underneath.
    # Mid-sentence on a wide-open mouth, and only once the TYPED line is the
    # one being spoken -- during the demo the window still holds the title.
    if 'talking' not in grabbed and not pending and mem[sym['nf']] \
            and mpu.pc == sym['flip']:
        f = mem[sym['f']]
        if f and mem[sym['fvis'] + f] == 4:
            grabbed['talking'] = True
            shot('shot-talking.png')
    if 'blink' not in grabbed and not pending and mem[sym['nf']] \
            and mpu.pc == sym['flip']:
        f = mem[sym['f']]
        if f and mem[sym['feye'] + f] == 2:
            grabbed['blink'] = True
            shot('shot-blink.png')
    # Every frame of the typed sentence, for the animation.
    if not pending and mem[sym['nf']] and mpu.pc == sym['flip']:
        f = mem[sym['f']]
        gif_frames.append((f, hgr(0x2000 if shown[0] == 2 else 0x4000)))
    if 'rest' not in grabbed and mpu.pc == sym['getline'] and not pending:
        grabbed['rest'] = True
        shot('shot-rest.png')
        break

print('wrote: %s' % ', '.join(sorted(grabbed)))

# ---- the animation, at the speed the card speaks it ----------------------
# flip is called just BEFORE the page becomes the displayed one, so the page
# captured above is the one about to be shown; its duration is the gap to the
# next frame in fsound, which the 6502 built itself.
nf = mem[sym['nf']]


def due(i):
    return (mem[sym['fsound'] + 2 * i] | (mem[sym['fsound'] + 2 * i + 1] << 8)) / 4.0


X0, X1, Y0, Y1 = 70, 212, 0, 160
imgs, durs = [], []
for f, pg in gif_frames:
    if f >= nf:
        continue
    im = Image.new('L', (X1 - X0, Y1 - Y0))
    im.putdata([255 if pg[y][x] else 0
                for y in range(Y0, Y1) for x in range(X0, X1)])
    imgs.append(im.resize(((X1 - X0) * SX, (Y1 - Y0) * SY), Image.NEAREST))
    durs.append(max(20, int(round(due(f + 1) - due(f)))))
if imgs:
    imgs[0].save('shot-talking.gif', save_all=True, append_images=imgs[1:],
                 duration=durs, loop=0)
    print('wrote shot-talking.gif: %d frames, %.2f s' % (len(imgs), sum(durs) / 1000))

# ---- the shapes, side by side ---------------------------------------------
def grid(path, group, labels, cols, crop, pad=8, lab=18):
    """The shapes side by side, each cropped to what actually moves."""
    x0, x1, y0, y1 = crop
    w, h = (x1 - x0) * SX, (y1 - y0) * SY
    rows = (len(group) + cols - 1) // cols
    im = Image.new('RGB', (cols * (w + pad) + pad,
                           rows * (h + lab + pad) + pad), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, pg in enumerate(group):
        cx = pad + (i % cols) * (w + pad)
        cy = pad + (i // cols) * (h + lab + pad)
        d.rectangle([cx - 1, cy - 1, cx + w, cy + h], outline=(60, 60, 60))
        for y in range(y0, y1):
            for x in range(x0, x1):
                if pg[y][x]:
                    d.rectangle([cx + (x - x0) * SX, cy + (y - y0) * SY,
                                 cx + (x - x0) * SX + SX - 1,
                                 cy + (y - y0) * SY + SY - 1],
                                fill=(255, 255, 255))
        d.text((cx + 2, cy + h + 3), labels[i], font=font, fill=(170, 170, 170))
    im.save(path)


both = [[[m | e for m, e in zip(rm, re)]
         for rm, re in zip(mkm.shapes[i], mkm.eyes[0])] for i in range(10)]
grid('shot-visemes.png', both, mkm.NAMES, 5, (103, 177, 86, 137))
eyes = [[[m | e for m, e in zip(rm, re)]
         for rm, re in zip(mkm.shapes[0], mkm.eyes[j])] for j in range(3)]
grid('shot-eyes.png', eyes, mkm.ENAMES, 3, (82, 198, 28, 80))
print('wrote shot-visemes.png and shot-eyes.png')
