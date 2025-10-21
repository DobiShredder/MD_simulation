#!/bin/bash

n_rep=`cat dist.list | wc -l`

cp ../rmd/prep/wat.parm7 .
for i in `seq 1 ${n_rep}`
do
	dist=`cat dist.list | sed -n ${i}p`
	cp -r temp ${i}
	cp ../rmd/snap/wat.rst7.${i} ${i}/wat.rst7
	cat temp/dist/dist.RST | sed "1,$ s/DIST/${dist}/g; s/FORCE/10/g" > ${i}/dist/dist.RST
	cd ${i} ; ln -s ../wat.parm7 ; cd ..

done
