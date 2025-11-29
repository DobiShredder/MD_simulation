#!/bin/bash

#min0
pmemd.cuda -O -i min0/min0.in -o min0/min0.out -p comp_wat.parm7 -c comp_wat.rst7 -r min0/min0.rst7 -ref comp_wat.rst7
#min1
pmemd.cuda -O -i min1/min1.in -o min1/min1.out -p comp_wat.parm7 -c min0/min0.rst7 -r min1/min1.rst7
#heat
pmemd.cuda -O -i heat/heat.in -o heat/heat.out -p comp_wat.parm7 -c min1/min1.rst7 -r heat/heat.rst7 -x heat/heat.nc -inf heat/heat.info

#LiGaMD
pmemd.cuda -O -i pepgamd/pepgamd.in -o pepgamd/pepgamd.out -p comp_wat.parm7 -c heat/heat.rst7 \
 -r pepgamd/pepgamd.rst7 -x pepgamd/pepgamd.nc -inf pepgamd/pepgamd.info -gamd pepgamd/pepgamd.log
