#!/bin/bash

repnum=`cat temp.list | wc -l`

#heat
mpirun -np $repnum pmemd.cuda.MPI -ng $repnum -groupfile heat.group -rem 0

#production
mpirun -np $repnum pmemd.cuda.MPI -ng $repnum -groupfile remd.group -rem 1
