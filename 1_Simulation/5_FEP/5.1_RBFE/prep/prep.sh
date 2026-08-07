#!/bin/bash

export PATH=$HOME/anaconda3/bin:$PATH
source activate pmx

pmx=/your_pmx_path/src/pmx/scripts
gmx=/your_gmx_path/bin/gmx

#$pmx/mutate.py -f apo.pdb -o mutant.pdb -ff amber99sb-star-ildn-mut
python3 mut.py

$gmx pdb2gmx -f mutant.pdb -o conf.pdb -ff amber99sb-star-ildn-mut -water tip3p
mv topol.top wt.top

$pmx/generate_hybrid_topology.py -p wt.top -o topol.top -ff amber99sb-star-ildn-mut

$gmx editconf -f conf.pdb -o box.pdb -bt cubic -d 1.4

$gmx solvate -cp box -cs spc216 -o water.pdb -p topol.top

$gmx grompp -f ions.mdp -c water.pdb -p topol.top -o ions.tpr

echo "SOL" | $gmx genion -s ions.tpr -o ions.gro -p topol.top -pname NA -nname CL -neutral -conc 0.15

$gmx grompp -f ions.mdp -c ions.gro -p topol.top -pp processed.top

cp ions.gro ../input.gro
cp processed.top ../topol.top
mv \#topol.top.1\# nowat.top

