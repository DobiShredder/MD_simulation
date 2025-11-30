#!/bin/bash

rm topol*.top
nrep=$@
tmin=298
tmax=598

list=$(awk -v n=$nrep \
    -v tmin=$tmin \
    -v tmax=$tmax \
    'BEGIN { for(i=0;i<n;i++) {
     t=tmin*exp(i*log(tmax/tmin)/(n-1));
     printf(t); if (i<n-1) printf(" ");
     }
}')
echo $list
for ((i=0;i<nrep;i++))
do
    let j=i+1
    lambda=$(echo $list | awk 'BEGIN {FS=" ";} {print $1/$'$((i+1))';}')
    echo $lambda
    plumed partial_tempering $lambda < prep/processed_mod.top > topol$j.top
done
