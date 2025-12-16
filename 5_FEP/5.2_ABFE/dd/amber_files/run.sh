#!/bin/bash

pmemd.cuda -O -i heat.in -p wat.parm7 -c wat.rst7 -ref wat.rst7 \
  -o heat.out -r heat.rst7 -x heat.nc -inf heat.info

pmemd.cuda -O -i eq.in -p wat.parm7 -c heat.rst7 -ref wat.rst7 \
  -o eq1.out -r eq1.rst7 -x eq1.nc -inf eq1.info

pmemd.cuda -O -i eq.in -p wat.parm7 -c eq1.rst7 -ref wat.rst7 \
  -o eq2.out -r eq2.rst7 -x eq2.nc -inf eq2.info

pmemd.cuda -O -i ti.in -p wat.parm7 -c heat.rst7 -ref wat.rst7 \
  -o ti.out -r ti.rst7 -x ti.nc -inf ti.info


