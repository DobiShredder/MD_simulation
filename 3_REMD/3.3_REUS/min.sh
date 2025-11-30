#!/bin/sh
#PBS -N NAME
#PBS -m ae
#PBS -q P100q
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

#min0
let num=`cat dist.dat | wc -l`
for i in `seq 1 $num`
do
        pmemd.cuda -O -i min0/min0.in.$i -p parm/comp_wat.parm7.$i -c parm/comp_wat.rst7.$i -o min0/min0.out.$i \
        -r min0/min0.rst7.$i -ref parm/comp_wat.rst7.$i

        pmemd.cuda -O -i min1/min1.in.$i -p parm/comp_wat.parm7.$i -c min0/min0.rst7.$i -o min1/min1.out.$i \
        -r min1/min1.rst7.$i
done
