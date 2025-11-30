#/bin/bash

mkdir -p ens
mkdir -p nowat
for i in `seq 1 40`
do
	cat nowat.temp | sed "1,$ s/REPNUM/$i/g" > nowat.$i
	cpptraj -i nowat.$i
	rm nowat.$i
done
cpptraj -i ens.in
