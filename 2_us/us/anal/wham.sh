#!/bin/bash

wham=~/kbs/util/wham/wham/wham
mkdir -p dat

beg=`head -n 1 ../dist.dat | awk '{print $1}'`
end=`tail -n 1 ../dist.dat | awk '{print $1}'`
temp=300
nbin=50
n_rep=`cat ../dist.list | wc -l`

for i in `seq 1 ${n_rep}`
do
        cat ../${i}/dist/dist.dat | awk '{print $1"\t"$8}' | tail -n +200000 > dat/dist.dat.$i
        file="dat/dist.dat.$i"
        dist=`cat ../dist.list | awk '{print $1}' | sed -n "${i}p"`
        force=`echo 10*2 | bc`
        echo $file $dist $force >> meta.dat
done

$wham $beg $end $nbin 0.000000001 $temp 0 meta.dat result.dat
rm meta.dat
