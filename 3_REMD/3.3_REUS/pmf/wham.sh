#!/bin/bash

wham=~/kbs/util/wham/wham/wham
rm meta.dat
mkdir -p dat

beg=`head -n 1 ../dist.dat`
end=`tail -n 1 ../dist.dat`
temp=300
nbin=160
wind=`cat ../dist.dat | wc -l`

for i in `seq 1 $wind`
do
        cat ../reus/dist.dat.$i | awk '{print $1"\t"$8}' | tail -n +200000 > dat/dist2.dat.$i
        file="dat/dist2.dat.$i"
        dist=`cat ../dist.dat | sed -n "${i}p"`
        force=2
        echo $file $dist $force >> meta.dat
done

$wham $beg $end $nbin 0.000000001 $temp 0 meta.dat result.dat
