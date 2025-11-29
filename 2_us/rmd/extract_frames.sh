#!/bin/bash

mkdir -p snap

n_rep=`cat dist.list | wc -l`
for i in `seq 1 $n_rep`
do
        d=`cat dist.list | sed -n "${i}p"`
        cat anal/dist.dat | tail -n +2 |
        awk -v b=$d 'BEGIN { min=60 } { dif=sqrt(($2-b)^2);
            if ( dif < min ) { min=dif ; num=NR ; dist=$2 } } END {print num, dist }' >> dist_sum.dat
done


prep_in="parm wat.parm7\n
trajin rmd/rmd.nc\n
autoimage :1\n
strip :WAT\n
strip :Na+\n
strip :Cl-"

echo -e ${prep_in} > prep.in

let num=1
for i in `cat dist_sum.dat | awk '{print $1}'`
do
        echo "trajout snap/rmd.pdb.${num} pdb onlyframes ${i}" >> prep.in
        let num=num+1
done
cpptraj -i prep.in
rm prep.in

rm dist_sum.dat

