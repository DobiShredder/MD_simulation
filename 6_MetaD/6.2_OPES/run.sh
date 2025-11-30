#!/bin/bash

pmemd.cuda -O -i min0/min0.in -o min0/min0.out -p wat.parm7 -c wat.rst7 -r min0/min0.rst7 -ref wat.rst7

pmemd.cuda -O -i min1/min1.in -o min1/min1.out -p wat.parm7 -c min0/min0.rst7 -r min1/min1.rst7 -ref wat.rst7

pmemd.cuda -O -i heat/heat.in -o heat/heat.out -p wat.parm7 -c min1/min1.rst7 -r heat/heat.rst7 \
 -x heat/heat.nc -inf heat/heat.info

pmemd.cuda -O -i opes/opes.in -p wat.parm7 -c heat/heat.rst7 \
  -o opes/opes.out -r opes/opes.rst7 -x opes/opes.nc -inf opes/opes.info

