#!/bin/bash

rm *.group
let num=`cat temp.dat | wc -l`
for i in `seq 1 $num`
do
    temp=`cat temp.dat | sed -n ${i}p`
    cat heat/heat.in | sed "1,$ s/RANDOMNUM/$random/g" | sed "1,$ s/%TEMP/$temp/g" > heat/heat.in.$i
    cat remd/remd.in | sed "1,$ s/RANDOMNUM/$random/g" | sed "1,$ s/%TEMP/$temp/g" > remd/remd.in.$i
    cat group.ref | sed -n 1p | sed "1,$ s/REPNUM/$i/g" >> heat.group
    cat group.ref | sed -n 2p | sed "1,$ s/REPNUM/$i/g" >> remd.group
    echo "" >> heat.group
    echo "" >> remd.group
done
