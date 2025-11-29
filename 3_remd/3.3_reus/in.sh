#!/bin/bash

rm *.group
let num=`cat dist.dat | wc -l`
for i in `seq 1 $num`
do
        cat min0/min0.in | sed "1,$ s/REPNUM/$i/g" > min0/min0.in.$i
        cat min1/min1.in | sed "1,$ s/REPNUM/$i/g" > min1/min1.in.$i
        cat heat/heat.in | sed "1,$ s/REPNUM/$i/g" > heat/heat.in.$i
        cat reus/reus.in | sed "1,$ s/REPNUM/$i/g" > reus/reus.in.$i
        cat group.ref | sed -n "1p" | sed "1,$ s/REPNUM/$i/g" >> heat.group
        cat group.ref | sed -n "2p" | sed "1,$ s/REPNUM/$i/g" >> reus.group
        echo "" >> heat.group
        echo "" >> reus.group
done

let j=1
for k in `cat dist.dat`
do
        filenum=$j
        num1=`echo $k | bc`
        num2=`echo $k | bc`
        cat dist/dist.RST | sed "1,$ s/NUM1/$num1/g" | sed "1,$ s/NUM2/$num2/g" > dist/dist.RST.$filenum
        let j=j+1
done
