#!/bin/bash
#PBS -N NAME
#PBS -m ae
#PBS -q workq
#PBS -l select=1:ncpus=20:ngpus=2:host=iremb-e-150+1:ncpus=20:ngpus=2:host=iremb-e-184+1:ncpus=20:ngpus=2:host=iremb-e-200+1:ncpus=20:ngpus=2:host=iremb-e-216+1:ncpus=20:ngpus=2:host=iremb-e-232+1:ncpus=20:ngpus=2:host=iremb-e-248+1:ncpus=20:ngpus=2:host=iremb-e-280+1:ncpus=20:ngpus=2:host=iremb-e-185+1:ncpus=20:ngpus=2:host=iremb-e-201+1:ncpus=20:ngpus=2:host=iremb-e-217+1:ncpus=20:ngpus=2:host=iremb-e-233+1:ncpus=20:ngpus=2:host=iremb-e-249+1:ncpus=20:ngpus=2:host=iremb-e-281+1:ncpus=20:ngpus=2:host=iremb-e-152

source ~/bashrc/kbs

cd $PBS_O_WORKDIR

export I_MPI_HYDRA_BOOTSTRAP=rsh
export I_MPI_HYDRA_BOOTSTRAP_EXEC=pbs_tmrsh
export I_MPI_FABRICS=shm:ofi

bash rest.sh

