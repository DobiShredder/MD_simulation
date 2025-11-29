#!/bin/bash

source ~/bashrc/kbs

pmemd.cuda -O -i min0.in -o min0.out -p wat.parm7 -c wat.rst7 -r min0.rst7 -ref wat.rst7

pmemd.cuda -O -i min1.in -o min1.out -p wat.parm7 -c min0.rst7 -r min1.rst7 -ref wat.rst7

pmemd.cuda -O -i heat.in -o heat.out -p wat.parm7 -c min1.rst7 -r heat.rst7 -x heat.nc -inf heat.info -ref wat.rst7


pmemd.cuda -O -i eq.in -o eq1.out -p wat.parm7 -c heat.rst7 -r eq1.rst7 -x eq1.nc -inf eq1.info -ref wat.rst7

for i in `seq 2 5`
do
    let j=i-1
    pmemd.cuda -O -i eq.in -o eq${i}.out -p wat.parm7 -c eq${j}.rst7 \
     -r eq${i}.rst7 -x eq${i}.nc -inf eq${i}.info -ref wat.rst7
done


if [ -f eq5.rst7 ];then
    cpptraj -i split.in
fi

