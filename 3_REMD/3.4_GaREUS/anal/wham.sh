#!/bin/bash

wham=~/kbs/util/wham/wham/wham
rm meta.dat
mkdir -p dat

beg=`head -n 1 ../dist.dat | awk '{print $1}'`
end=`tail -n 1 ../dist.dat | awk '{print $1}'`
temp=300
nbin=70
wind=`cat ../dist.dat | wc -l`

for i in `seq 1 $wind`
do
        cat ../dist/dist.dat.$i | awk '{print $1"\t"$8}' | head -n900000 | tail -n +200000 > dat/dist2.dat.$i
        file="dat/dist2.dat.$i"
        dist=`cat ../dist.dat | awk '{print $1}' | sed -n "${i}p"`
        force1=`cat ../dist.dat | awk '{print $2}' | sed -n "${i}p"`
        force=`echo 2*${force1} | bc`
        echo $file $dist $force >> meta.dat
done

$wham $beg $end $nbin 0.000000001 $temp 0 meta.dat result.dat
