#!/bin/bash
#PBS -N NAME
#PBS -m ae
#PBS -q P100q
#PBS -l select=1:ncpus=2:ngpus=2:host=iremb-e-252+1:ncpus=2:ngpus=2:host=iremb-e-268+1:ncpus=2:ngpus=2:host=iremb-e-189+1:ncpus=2:ngpus=2:host=iremb-e-205+1:ncpus=2:ngpus=2:host=iremb-e-221+1:ncpus=2:ngpus=2:host=iremb-e-237+1:ncpus=2:ngpus=2:host=iremb-e-253+1:ncpus=2:ngpus=2:host=iremb-e-269+1:ncpus=2:ngpus=2:host=iremb-e-285+1:ncpus=2:ngpus=2:host=iremb-e-156+1:ncpus=2:ngpus=2:host=iremb-e-286+1:ncpus=2:ngpus=2:host=iremb-e-287+1:ncpus=2:ngpus=2:host=iremb-e-288+1:ncpus=2:ngpus=2:host=iremb-e-137

cd $PBS_O_WORKDIR
ulimit -s unlimited

source ~/bashrc/kbs

export I_MPI_HYDRA_BOOTSTRAP=rsh
export I_MPI_HYDRA_BOOTSTRAP_EXEC=pbs_tmrsh
export I_MPI_FABRICS=shm:ofi


let n_rep=`cat dist.dat | wc -l`

#heat
mpirun -np $n_rep pmemd.cuda.MPI -ng $n_rep -groupfile heat.group -rem 0
#reus
mpirun -np $n_rep pmemd.cuda.MPI -ng $n_rep -groupfile gareus.group -rem 3

