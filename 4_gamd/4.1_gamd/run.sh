#!/bin/bash

#min0
pmemd.cuda -O -i min0/min0.in -o min0/min0.out -p wat.parm7 -c wat.rst7 -r min0/min0.rst7 -ref wat.rst7
#min1
pmemd.cuda -O -i min1/min1.in -o min1/min1.out -p wat.parm7 -c min0/min0.rst7 -r min1/min1.rst7
#heat
pmemd.cuda -O -i heat/heat.in -o heat/heat.out -p wat.parm7 -c min1/min1.rst7 -r heat/heat.rst7 -x heat/heat.nc -inf heat/heat.info

#GaMD
pmemd.cuda -O -i gamd/gamd1.in -o gamd/gamd1.out -p wat.parm7 -c heat/heat.rst7 \
 -r gamd/gamd1.rst7 -x gamd/gamd1.nc -inf gamd/gamd1.info -gamd gamd/gamd1.log

pmemd.cuda -O -i gamd/gamd2.in -o gamd/gamd2.out -p wat.parm7 -c gamd/gamd1.rst7 \
 -r gamd/gamd2.rst7 -x gamd/gamd2.nc -inf gamd/gamd2.info -gamd gamd/gamd2.log

