#!/bin/bash
#PBS -N NAME
#PBS -m ae
#PBS -q P100q
#PBS -l select=1:ncpus=20:ngpus=2:host=iremb-e-150+1:ncpus=20:ngpus=2:host=iremb-e-184+1:ncpus=20:ngpus=2:host=iremb-e-200+1:ncpus=20:ngpus=2:host=iremb-e-216+1:ncpus=20:ngpus=2:host=iremb-e-232+1:ncpus=20:ngpus=2:host=iremb-e-248+1:ncpus=20:ngpus=2:host=iremb-e-280+1:ncpus=20:ngpus=2:host=iremb-e-185+1:ncpus=20:ngpus=2:host=iremb-e-201+1:ncpus=20:ngpus=2:host=iremb-e-217+1:ncpus=20:ngpus=2:host=iremb-e-233+1:ncpus=20:ngpus=2:host=iremb-e-249+1:ncpus=20:ngpus=2:host=iremb-e-281+1:ncpus=20:ngpus=2:host=iremb-e-152

cd $PBS_O_WORKDIR
ulimit -s unlimited

source ~/bashrc/kbs

export I_MPI_HYDRA_BOOTSTRAP=rsh
export I_MPI_HYDRA_BOOTSTRAP_EXEC=pbs_tmrsh
export I_MPI_FABRICS=shm:ofi


let n_rep=`cat dist.list | wc -l`

#heat
mpirun -np $n_rep pmemd.cuda.MPI -ng $n_rep -groupfile heat.group -rem 0
#reus
mpirun -np $n_rep pmemd.cuda.MPI -ng $n_rep -groupfile reus.group -rem 3
