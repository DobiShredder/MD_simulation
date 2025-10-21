#!/bin/bash

n_rep=`cat dist.list | wc -l`
for i in `seq 1 $n_rep`
do
        d=`cat dist.list | sed -n "${i}p"`
        cat dist.dat | tail -n +2 |
        awk -v b=$d 'BEGIN { min=60 } { dif=sqrt(($2-b)^2);
            if ( dif < min ) { min=dif ; num=NR ; dist=$2 } } END {print num, dist }' >> dist_sum.dat
done

let num=1
for j in `cat dist_sum.dat | awk '{print $1}'`
do
        echo "parm wat.parm7" > prep$num.in
        echo "trajin rmd/rmd.nc $j $j 1" >> prep$num.in
        echo "autoimage :1" >> prep$num.in
        echo "trajout snap/wat.rst7.$num restart" >> prep$num.in
        cpptraj -i prep$num.in
        rm prep$num.in
        let num=num+1
done

rm dist_sum.dat
