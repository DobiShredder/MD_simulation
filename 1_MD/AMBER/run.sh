#!/bin/bash

### Before running MD, you should change RESNUM in 'min0.in' file

pmemd.cuda -O -i min0/min0.in -o min0/min0.out -p wat.parm7 -c wat.rst7 -r min0/min0.rst7 -ref wat.rst7

pmemd.cuda -O -i min1/min1.in -o min1/min1.out -p wat.parm7 -c min0/min0.rst7 -r min1/min1.rst7 -ref wat.rst7

pmemd.cuda -O -i heat/heat.in -o heat/heat.out -p wat.parm7 -c min1/min1.rst7 -r heat/heat.rst7 \
 -x heat/heat.nc -inf heat/heat.info

pmemd.cuda -O -i md/md.in -o md/md1.out -p wat.parm7 -c heat/heat.rst7 -r md/md1.rst7 \
 -x md/md1.nc -inf md/md1.info

for i in `seq 2 10`
do
    let j=i-1
	pmemd.cuda -O -i md/md.in -o md/md$i.out -p wat.parm7 -c md/md$j.rst7 -r md/md$i.rst7 \
	 -x md/md$i.nc -inf md/md$i.info
done

