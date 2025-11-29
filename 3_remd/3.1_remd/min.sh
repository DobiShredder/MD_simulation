#!/bin/bash

source ~/bashrc/kbs

pmemd.cuda -O -i min0/min0.in -p wat.parm7 -c wat.rst7 -o min0/min0.out \
 -r min0/min0.rst7 -ref wat.rst7

pmemd.cuda -O -i min1/min1.in -p wat.parm7 -c min0/min0.rst7 -o min1/min1.out \
 -r min1/min1.rst7


