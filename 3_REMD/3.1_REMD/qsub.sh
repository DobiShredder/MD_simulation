#/bin/bash
#PBS -N NAME
#PBS -m ae
#PBS -q P100q
#PBS -l select=10:ncpus=2:ngpus=2

cd $PBS_O_WORKDIR
ulimit -s unlimited

source ~/bashrc/kbs

export I_MPI_HYDRA_BOOTSTRAP=rsh
export I_MPI_HYDRA_BOOTSTRAP_EXEC=pbs_tmrsh
export I_MPI_FABRICS=shm:ofi

bash run.sh

