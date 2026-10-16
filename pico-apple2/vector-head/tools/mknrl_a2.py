"""Turn the firmware's NRL rules into 6502 data.

The card cannot be read back -- the 74LVC245 faces one way and there is no
status register -- so the Apple II cannot ask it what allophones a sentence
came out as.  If the head is to lip-sync text the operator types, the letter-
to-sound rules have to run on the 6502 as well.

Which means two implementations of the same rules, and the only safe way to
have two is to generate one from the other.  This reads nrl.c itself: the rule
table, the exception list and the phoneme numbering all come out of the C
source, so a rule fixed in the firmware is fixed here by rebuilding.

The output of a rule is stored as phoneme NUMBERS rather than as the ARPAbet
text nrl.c emits.  nrl.c writes text and stage 2 tokenises it straight back;
doing that lookup here instead saves the 6502 a parser and about 700 bytes.

Rule, as stored:
    lenL lenM lenR lenO  <left> <match> <right> <out>
with $FF in the first byte ending a group.  Groups are indexed by the letter
being matched, punctuation last, exactly as rule_groups[] does it.
"""
import re, sys, os

# The firmware's own rules, two directories up: generating from them is what
# keeps the card and the Apple II saying the same thing.
NRL_C = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '..', '..', 'sp0256', 'nrl.c')
src = open(NRL_C).read()

# ---- the phoneme numbering, taken from the enum rather than assumed --------
enum = src[src.index('enum {\n  P_IY'):]
enum = enum[:enum.index('};')]
PH = [t.strip()[2:] for t in re.split(r'[,\n]', enum)
      if t.strip().startswith('P_')]
PHID = {n: i for i, n in enumerate(PH)}
P_BOUND, P_NONE = PHID['BOUND'], PHID['NONE']

# ---- and the ARPAbet spellings, from phon_name[] ---------------------------
names = src[src.index('phon_name[] = {'):]
names = names[:names.index('};')]
NAME = re.findall(r'"([^"]*)"', names)
assert len(NAME) == P_BOUND + 1, (len(NAME), P_BOUND)
TOKID = {t: i for i, t in enumerate(NAME)}


def out_bytes(s):
    """An ARPAbet output string as phoneme numbers."""
    if s == ' ':
        return [P_BOUND]
    ids = []
    for tok in s.split():
        if tok not in TOKID:
            raise SystemExit('unknown phoneme %r in rule output %r' % (tok, s))
        ids.append(TOKID[tok])
    return ids


# ---- the rules, group by group --------------------------------------------
RULE = re.compile(r'\{\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,'
                  r'\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\}')
GROUPS = ['rules_%s' % c.lower() for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] + \
         ['rules_punct']

blob, index, total = bytearray(), [], 0
for g in GROUPS:
    start = src.index('%s[] = {' % g)
    end = src.index('};', start)
    index.append(len(blob))
    n = 0
    for left, match, right, out in RULE.findall(src[start:end]):
        ob = out_bytes(out)
        if max(len(left), len(match), len(right), len(ob)) > 254:
            raise SystemExit('field too long in %s' % g)
        blob += bytes([len(left), len(match), len(right), len(ob)])
        blob += left.encode() + match.encode() + right.encode() + bytes(ob)
        n += 1
    blob.append(0xFF)
    total += n

# ---- the exception table ---------------------------------------------------
fx = src[src.index('nrl_fix_t fixes[] = {'):]
fx = fx[:fx.index('\n};')]
fixes = re.findall(r'\{\s*"([A-Z\']+)"\s*,\s*"([A-Z \']+)"\s*\}', fx)

# Digits become words, with a space either side, exactly as prepare() does.
dw = src[src.index('digit_words[10] = {'):]
dw = dw[:dw.index('};')]
DIGITS = re.findall(r'"([A-Z]+)"', dw)
assert len(DIGITS) == 10, DIGITS
digblob = bytearray()
digoff = []
for d in DIGITS:
    digoff.append(len(digblob))
    t = ' ' + d + ' '
    digblob += bytes([len(t)]) + t.encode()

fixblob = bytearray()
for word, said in fixes:
    fixblob += bytes([len(word), len(said)]) + word.encode() + said.encode()
fixblob.append(0)

# ---- character classes, one table instead of five predicates --------------
# bit 0 vowel, 1 consonant, 2 voiced, 3 front.  These mirror is_vowel,
# is_consonant, is_voiced and is_front in nrl.c; the corpus test is what keeps
# them honest, since a table cannot be parsed out of C predicates safely.
VOWEL = 'AEIOU'
VOICED = 'BDVGJLMNRWZ'
FRONT = 'EIY'
cls = []
for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    v = 0
    if ch in VOWEL:
        v |= 1
    else:
        v |= 2
    if ch in VOICED:
        v |= 4
    if ch in FRONT:
        v |= 8
    cls.append(v)

# ---- AL2 codes and phoneme classes, both out of nrl.c --------------------
al2 = src[src.index('enum {\n  A_PA1'):]
al2 = al2[:al2.index('};')]
A = {}
for m in re.finditer(r'A_(\w+)\s*=\s*(\d+)', al2):
    A[m.group(1)] = int(m.group(2))
assert len(A) == 64, len(A)

# bit 0 vowel, 1 front vowel, 2 plosive -- mirroring is_vowel_phon,
# is_front_vowel and is_plosive in nrl.c.
FRONTV = ['IY', 'IH', 'EY', 'EH', 'AE', 'AY']
PLOSIVE = ['p', 'b', 't', 'd', 'k', 'g', 'CH', 'j']
phcls = []
for i, n in enumerate(PH[:P_BOUND + 1]):
    v = 0
    if i <= PHID['OY']:
        v |= 1
    if n in FRONTV:
        v |= 2
    if n in PLOSIVE:
        v |= 4
    phcls.append(v)

# The AL2 code for each phoneme, or $FF where the choice depends on position.
SIMPLE = {'IY': 'IY', 'IH': 'IH', 'EY': 'EY', 'EH': 'EH', 'AE': 'AE',
          'AA': 'AA', 'AO': 'AO', 'OW': 'OW', 'UH': 'UH', 'AX': 'AX',
          'AH': 'AX', 'AY': 'AY', 'AW': 'AW', 'OY': 'OY', 'p': 'PP',
          'f': 'FF', 'v': 'VV', 'TH': 'TH', 's': 'SS', 'z': 'ZZ',
          'SH': 'SH', 'ZH': 'ZH', 'm': 'MM', 'NG': 'NG', 'w': 'WW',
          'WH': 'WH', 'CH': 'CH', 'j': 'JH'}
simple = [A[SIMPLE[n]] if n in SIMPLE else 0xFF for n in PH[:P_BOUND + 1]]

here = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
# The data is a file of its own, BLOADed at $1000, because the head binary has
# no room left: it already runs from $6000 to within a page of where ProDOS
# starts.  Python knows the layout, so the addresses are emitted as equates and
# nothing has to be exported across two separate links.
NRL_ORG = 0x0C00

def block(name, data, out, addrs):
    addrs[name] = NRL_ORG + len(out)
    out += data

blob_out = bytearray()
addrs = {}
gidx = bytearray()
for off in index:
    gidx += bytes([off & 0xFF, off >> 8])
block('nrl_group_tab', gidx, blob_out, addrs)
block('nrl_rules', blob, blob_out, addrs)
block('nrl_class', bytes(cls), blob_out, addrs)
block('ph_class', bytes(phcls), blob_out, addrs)
block('ph_al2', bytes(simple), blob_out, addrs)
block('nrl_digit_off', bytes(digoff), blob_out, addrs)
block('nrl_digits', bytes(digblob), blob_out, addrs)
block('nrl_fixes', bytes(fixblob), blob_out, addrs)

with open(os.path.join(here, 'nrldata.s'), 'w') as f:
    f.write('; Generated by mknrl_a2.py from nrl.c -- do not edit.\n'
            '; The NRL tables, assembled on their own and BLOADed at $%04X.\n'
            '; %d rules in %d groups.\n\n' % (NRL_ORG, total, len(GROUPS)))
    f.write('        .org $%04X\n\n' % NRL_ORG)
    for j in range(0, len(blob_out), 16):
        f.write('        .byte ' + ','.join('$%02X' % v for v in blob_out[j:j + 16])
                + '\n')

with open(os.path.join(here, 'nrlsym.inc'), 'w') as f:
    f.write('; Generated by mknrl_a2.py from nrl.c -- do not edit.\n'
            '; Where everything landed in nrldata.s, and the numbering both\n'
            '; sides have to agree on.\n\n')
    f.write('NRL_ORG    = $%04X\nNRL_LEN    = %d\nNRL_NGROUP = %d\n\n'
            % (NRL_ORG, len(blob_out), len(GROUPS)))
    for n in ('nrl_group_tab', 'nrl_rules', 'nrl_class', 'ph_class', 'ph_al2',
              'nrl_digit_off', 'nrl_digits', 'nrl_fixes'):
        f.write('%-14s= $%04X\n' % (n, addrs[n]))
    f.write('\n')
    for n, v in sorted(A.items()):
        f.write('A_%-4s= %d\n' % (n, v))
    f.write('\n')
    for n, v in sorted(PHID.items(), key=lambda kv: kv[1]):
        f.write('P_%-4s= %d\n' % (n, v))

print('%d rules, %d groups' % (total, len(GROUPS)))
print('rule blob   : %d bytes' % len(blob))
print('group index : %d bytes' % (2 * len(index)))
print('exceptions  : %d entries, %d bytes' % (len(fixes), len(fixblob)))
print('nrldata.s   : %d bytes at $%04X..$%04X'
      % (len(blob_out), NRL_ORG, NRL_ORG + len(blob_out) - 1))
print('phonemes    : %d, boundary = %d' % (P_BOUND, P_BOUND))
