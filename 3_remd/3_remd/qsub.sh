#/bin/bash
#PBS -N tremd_M-Ab75
#PBS -m ae
#PBS -q workq
#PBS -l nodes=iremb-e-223:ppn=2+iremb-e-161:ppn=2+iremb-e-255:ppn=2+iremb-e-141:ppn=2+iremb-e-239:ppn=2+iremb-e-175:ppn=2+iremb-e-207:ppn=2+iremb-e-191:ppn=2+iremb-e-174:ppn=2+iremb-e-254:ppn=2+iremb-e-270:ppn=2+iremb-e-238:ppn=2+iremb-e-222:ppn=2+iremb-e-206:ppn=2+iremb-e-159:ppn=2+iremb-e-190:ppn=2+iremb-e-140:ppn=2+iremb-e-158:ppn=2+iremb-e-139:ppn=2+iremb-e-138:ppn=2

cd $PBS_O_WORKDIR
ulimit -s unlimited

source ~/bashrc/kbs

export I_MPI_HYDRA_BOOTSTRAP=rsh
export I_MPI_HYDRA_BOOTSTRAP_EXEC=pbs_tmrsh
export I_MPI_FABRICS=shm:ofi


repnum=`cat temp.dat | wc -l`

#heat
mpirun -np $repnum pmemd.cuda.MPI -ng $repnum -groupfile heat.group -rem 0

#production
mpirun -np $repnum pmemd.cuda.MPI -ng $repnum -groupfile remd.group -rem 1
