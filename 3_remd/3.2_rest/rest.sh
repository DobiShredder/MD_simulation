#!/bin/bash

export OMP_NUM_THREADS=10

let REP=`ls topol*.top | wc -l`
let NP=2*$REP
list=( `seq 1 $REP` )
gmx="mpirun -np $NP gmx_mpi"

# step1 - Minimization
mkdir -p step3
cd step3
for i in `seq 1 $REP`
do
    mkdir -p min$i
    gmx_mpi grompp -f ../step4.0_minimization.mdp -o min$i/min.tpr -c ../step3_input.gro -r ../step3_input.gro -p ../topol$i.top -maxwarn 5
done
cd ..

cd step3
$gmx mdrun -multidir ${list[@]/#/min} -v -deffnm min -ntomp $OMP_NUM_THREADS -pin on -nb gpu
cd ..

# step2 - Equilibrium
mkdir -p step4
cd step4
for i in `seq 1 $REP`
do
    mkdir -p eq$i
    gmx_mpi grompp -f ../step4.1_equilibration.mdp -o eq$i/eq.tpr -c ../step3/min$i/min.gro -r ../step3_input.gro -p ../topol$i.top -maxwarn 5
done
cd ..

cd step4
$gmx mdrun -multidir ${list[@]/#/eq} -deffnm eq -v -ntomp $OMP_NUM_THREADS -pin on -nb gpu -replex 0 -nex 0
cd ..


# step3 - MD run
mkdir -p step5
cd step5
for i in `seq 1 $REP`
do
    mkdir -p rest$i
    cp ../plumed.dat rest$i/
    gmx_mpi grompp -f ../step5_production.mdp -o rest$i/rest1.tpr -c ../step4/eq$i/eq.gro -p ../topol$i.top -maxwarn 5
done

# MD first run
$gmx mdrun -plumed plumed.dat -multidir ${list[@]/#/rest} -deffnm rest1 -v -replex 1000 -nsteps 100000000 -hrex -dlb no -ntomp $OMP_NUM_THREADS -nb gpu


for i in `seq 2 5`
do
    let k=i-1
    # MD extending run
    for j in `seq 1 $REP`
    do
        gmx_mpi grompp -f ../step5_production.mdp -o rest${j}/rest${i}.tpr -c rest${j}/rest${k}.tpr -p ../topol${j}.top -maxwarn 5
    done
    $gmx mdrun -plumed plumed.dat -multidir ${list[@]/#/rest} -deffnm rest${i} -v -replex 1000 -nsteps 100000000 -hrex -dlb no -ntomp $OMP_NUM_THREADS -nb gpu -cpi rest${k}.cpt -noappend

done
cd ..

unset OMP_NUM_THREADS
