#!/bin/bash

input="1uao.pdb"
gmx="gmx_mpi"

$gmx pdb2gmx -f $input -o apo.gro -water tip3p -ignh <<EOF
6
EOF

$gmx editconf -f apo.gro -o newbox.gro -c -d 1.4 -bt cubic

$gmx solvate -cp newbox.gro -cs spc216.gro -o solv.gro -p topol.top

$gmx grompp -f ions.mdp -c solv.gro -p topol.top -o ions.tpr

$gmx genion -s ions.tpr -o ions.gro -p topol.top -pname NA -nname CL -neutral -conc 0.15 <<EOF
SOL
EOF

$gmx grompp -f ions.mdp -c ions.gro -p topol.top -pp processed.top

cp ions.gro ../step3_input.gro
mv \#topol.top.1\# nowat.top
#rm \#*

python3 convert.py
