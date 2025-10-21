#!/bin/bash

n_rep=`cat dist.list | wc -l`

for i in `seq 1 ${n_rep}`
do
	cd $i
	bash run.sh
	cd ..
done

