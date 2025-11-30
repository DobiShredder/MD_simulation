#!/bin/bash

#min0
pmemd.cuda -O -i min0/min0.in -o min0/min0.out -p wat.parm7 -c wat.rst7 -r min0/min0.rst7 -ref wat.rst7
#min1
pmemd.cuda -O -i min1/min1.in -o min1/min1.out -p wat.parm7 -c min0/min0.rst7 -r min1/min1.rst7
#heat
pmemd.cuda -O -i heat/heat.in -o heat/heat.out -p wat.parm7 -c min1/min1.rst7 -r heat/heat.rst7 -x heat/heat.nc -inf heat/heat.info
#equilibration
pmemd.cuda -O -i eq/ligamd-eq.in -o eq/eq.out -p wat.parm7 -c heat/heat.rst7 -r eq/eq.rst7 -x eq/eq.nc -inf eq/eq.info -gamd eq/eq.log

#LiGaMD3
pmemd.cuda -O -i ligamd/ligamd.in -o ligamd/ligamd.out -p wat.parm7 -c eq/eq.rst7 \
 -r ligamd/ligamd.rst7 -x ligamd/ligamd.nc -inf ligamd/ligamd.info -gamd ligamd/ligamd.log

for i in `seq 2 5`
do
    let j=i-1
    pmemd.cuda -O -i ligamd/ligamd.in -o ligamd/ligamd${i}.out -p wat.parm7 -c ligamd/ligamd${j}.rst7 \
     -r ligamd/ligamd${i}.rst7 -x ligamd/ligamd${i}.nc -inf ligamd/ligamd${i}.info -gamd ligamd/ligamd${i}.log
done

