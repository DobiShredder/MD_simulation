#!/bin/bash

export PATH=$HOME/anaconda3/bin:$PATH
source activate alchem

source ~/bashrc/kbs

cd prep

python3 com.py -i nowat.pdb -o aligned.pdb
cat aligned.pdb | grep -v HETATM > prot.pdb
cat aligned.pdb | grep HETATM > lig.pdb
tleap -f leap.src

cd ..

ln -s prep/wat.parm7
ln -s prep/wat.rst7

let resnum=`cat prep/GB.pdb | grep CA | tail -n1 | awk '{print $5}'`
let res_num=resnum+1
cv_num=`cat prep/GB.pdb | grep "ATOM" | grep -v "LIG" | grep -v "DUM" |
        awk 'BEGIN { num=0 } { if ( $3=="C" || $3=="O" || $3=="CA" || $3=="N" ) num+=1 } END {print num+2}'`
cv_atoms=`cat prep/GB.pdb | grep "ATOM" | grep -v "LIG" |
          awk 'BEGIN { printf "1,0," } { if ( $3=="C" || $3=="O" || $3=="CA" || $3=="N") printf "%s,", $2}'`

cat amber_files/cv.in | sed "1,$ s/CV_NUM/$cv_num/g;s/ATOM_NUM/$cv_atoms/g" > cv.in
cat amber_files/min0.in | sed "1,$ s/RESNUM/$res_num/g" > min0.in
cat amber_files/min1.in  > min1.in
cat amber_files/heat.in  > heat.in
cat amber_files/eq.in > eq.in
cat amber_files/split.in | sed "1,$ s/RESNUM/$res_num/g" > split.in

