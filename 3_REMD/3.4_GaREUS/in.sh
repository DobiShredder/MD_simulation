#!/bin/bash

rm *.group

let num=`cat dist.dat | wc -l`

for i in `seq 1 $num`
do
        cat min0/min0.in | sed "1,$ s/REPNUM/$i/g" > min0/min0.in.$i
        cat min1/min1.in | sed "1,$ s/REPNUM/$i/g" > min1/min1.in.$i
        cat heat/heat.in | sed "1,$ s/REPNUM/$i/g" > heat/heat.in.$i
        cat gareus/gareus.in | sed "1,$ s/REPNUM/$i/g" > gareus/gareus.in.$i
        cat group.ref | sed -n "1p" | sed "1,$ s/REPNUM/$i/g" >> heat.group
        cat group.ref | sed -n "2p" | sed "1,$ s/REPNUM/$i/g" >> gareus.group
        echo "" >> heat.group
        echo "" >> gareus.group
done

for k in `seq 1 $num`
do
        dist=`cat dist.dat | sed -n "${k}p" | awk '{print $1}'`
        force=`cat dist.dat | sed -n "${k}p" | awk '{print $2}'`
        cat dist/dist.RST | sed "1,$ s/DIST/$dist/g" | sed "1,$ s/FORCE/$force/g" > dist/dist.RST.$k
done

