#/bin/bash
#PBS -N NAME
#PBS -m ae
#PBS -q workq
#PBS -l select=1:ncpus=1:ngpus=1

gid0=`nvidia-smi pmon -c 1 | awk 'BEGIN{i=0}{if($1==0&&$2>0) i+=1}END{print i}'`
gid1=`nvidia-smi pmon -c 1 | awk 'BEGIN{i=0}{if($1==1&&$2>0) i+=1}END{print i}'`
let gid=-1
if [ $gid1 -eq 0 ]
    then
    let gid=1
    elif [ $gid0 -eq 0 ]
    then
    let gid=0
fi

export CUDA_VISIBLE_DEVICES="$gid"
cd $PBS_O_WORKDIR
ulimit -s unlimited

source ~/bashrc/kbs

bash run.sh

