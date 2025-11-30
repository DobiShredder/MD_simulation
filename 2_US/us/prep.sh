#!/bin/bash

n_rep=`cat dist.list | wc -l`

for i in `seq 1 ${n_rep}`
do
	dist=`cat dist.list | awk '{print $1}' | sed -n ${i}p`
	force=`cat dist.list | awk '{print $2}' | sed -n ${i}p`
	cp -r temp ${i}
	cp ../rmd/snap/rmd.pdb.${i} ${i}/prep/rmd.pdb
	cat temp/dist/dist.RST | sed "1,$ s/DIST/${dist}/g; s/FORCE/${force}/g" > ${i}/dist/dist.RST
	cd ${i}/prep; tleap -f leap.src; cd ..; ln -s prep/wat.parm7; ln -s prep/wat.rst7; cd ..
done
