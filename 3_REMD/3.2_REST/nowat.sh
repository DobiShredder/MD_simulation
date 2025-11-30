#!/bin/bash

let repnum=`ls topol*.top | wc -l`
mkdir -p anal
cd anal
for i in `seq 1 $repnum`
do
    gmx_mpi trjconv -s ../step5/rest$i/rest.tpr -f ../step5/rest$i/rest.xtc -o ./xtc/nowat.$i.xtc -pbc mol -boxcenter rect << EOF
1
1
EOF
done
cd ..
