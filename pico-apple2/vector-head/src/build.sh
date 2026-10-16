#!/bin/sh
# Build the vector head.  Needs cc65's ca65 and ld65 -- nothing else.
#
# Two binaries, because one would not fit: the head runs from $6000 to within
# a page of ProDOS, so the NRL rule tables live in a file of their own down at
# $0C00.  The loader BLOADs that one and BRUNs this one.
set -e
cd "$(dirname "$0")"

ca65 -g -o vhead.o  vhead.s
ld65 -t none -Ln vhead.lbl -o vhead.bin vhead.o

ca65    -o nrldata.o nrldata.s
ld65 -t none -o nrldata.bin nrldata.o

printf 'vhead.bin   %6d bytes at $6000\n' "$(wc -c < vhead.bin)"
printf 'nrldata.bin %6d bytes at $0C00\n' "$(wc -c < nrldata.bin)"
