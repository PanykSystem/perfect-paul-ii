#!/bin/sh
# Everything that can be checked without an Apple II.
#
# The rules test is the one that matters: there are two implementations of the
# same letter-to-sound rules -- nrl.c on the card and nrl.inc here -- and the
# only thing that keeps two implementations honest is running both.  It needs
# the firmware's host build as its oracle.
set -e
cd "$(dirname "$0")"

[ -x ../../sp0256/host/nrl_test ] || make -C ../../sp0256/host nrl_test
sh ../src/build.sh

ca65 -g -I ../src -o nrltest.o nrltest.s
ld65 -t none -Ln nrltest.lbl -o nrltest.bin nrltest.o
cp ../src/nrldata.bin .

PY=${PYTHON:-python3}
echo; echo '== the rules, against the firmware =='   ; $PY nrltest.py
echo; echo '== the delay loop =='                     ; $PY cal_delay.py
echo; echo '== every shape, and every frame drawn ==' ; $PY run2.py
echo; echo '== typed text, end to end =='             ; $PY run3.py
echo; echo '== blinking while it waits =='            ; $PY run_idle.py
echo; echo '== nothing uninitialised on screen =='    ; $PY run_text.py
echo; echo '== sync, with the delays running =='      ; $PY run_time3.py
