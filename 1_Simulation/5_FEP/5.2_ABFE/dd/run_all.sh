#!/bin/bash

for i in `cat list`
do
    cd $i
    bash run.sh
    cd ..
done
