#!/bin/bash

pmemd.cuda -O -i min0/min0.in -o min0/min0.out -p wat.parm7 -c wat.rst7 -r min0/min0.rst7 -ref wat.rst7

pmemd.cuda -O -i min1/min1.in -o min1/min1.out -p wat.parm7 -c min0/min0.rst7 -r min1/min1.rst7 -ref wat.rst7

pmemd.cuda -O -i heat/heat.in -o heat/heat.out -p wat.parm7 -c min1/min1.rst7 -r heat/heat.rst7 \
 -x heat/heat.nc -inf heat/heat.info

pmemd.cuda -O -i metad/metad.in -p wat.parm7 -c heat/heat.rst7 \
  -o metad/metad.out -r metad/metad.rst7 -x metad/metad.nc -inf metad/metad.info

