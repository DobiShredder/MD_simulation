#!/bin/bash

export OMP_NUM_THREADS=10

gmx=gmx_mpi
let lambda=20


# 1 Energy Minimization
mkdir -p 1_min
for i in `seq 0 $lambda`
do
	cd 1_min
	mkdir -p min${i}
	cat ../min.mdp | sed "1,$ s/LAMBDA/${i}/g" > min${i}/min${i}.mdp
	$gmx grompp -f min${i}/min${i}.mdp -c ../input.gro -r ../input.gro -p ../topol.top -o min${i}/min${i}.tpr -maxwarn 10
	cd ..
done

for i in `seq 0 $lambda`
do
	cd 1_min/min${i}
	mpirun -np 2 $gmx mdrun -v -deffnm min${i} -pin on -nb gpu -ntomp $OMP_NUM_THREADS
	cd ../..
done


# 2 Equilibration
mkdir -p 2_eq
for i in `seq 0 $lambda`
do
	cd 2_eq
	mkdir -p eq${i}
	cat ../eq.mdp | sed "1,$ s/LAMBDA/${i}/g" > eq${i}/eq${i}.mdp
	$gmx grompp -f eq${i}/eq${i}.mdp -c ../1_min/min${i}/min${i}.gro -r ../1_min/min${i}/min${i}.gro -p ../topol.top -o eq${i}/eq${i}.tpr -maxwarn 10
	cd ..
done

for i in `seq 0 $lambda`
do
	cd 2_eq/eq${i}
	mpirun -np 2 $gmx mdrun -v -deffnm eq${i} -pin on -nb gpu -ntomp $OMP_NUM_THREADS
	cd ../..
done


# 3 TI production
mkdir -p 3_ti
for i in `seq 0 $lambda`
do
	cd 3_ti
	mkdir -p ti${i}
	cat ../ti.mdp | sed "1,$ s/LAMBDA/${i}/g" > ti${i}/ti${i}.mdp
	$gmx grompp -f ti${i}/ti${i}.mdp -c ../2_eq/eq${i}/eq${i}.gro -p ../topol.top -o ti${i}/ti${i}.tpr -maxwarn 10
	cd ..
done

for i in `seq 0 $lambda`
do
	cd 3_ti/ti${i}
	mpirun -np 2 $gmx mdrun -v -deffnm ti${i} -pin on -nb gpu -ntomp $OMP_NUM_THREADS
	cd ../..
done

$gmx bar -f 3_ti/ti*/ti*.xvg -o -oi

unset OMP_NUM_THREADS
