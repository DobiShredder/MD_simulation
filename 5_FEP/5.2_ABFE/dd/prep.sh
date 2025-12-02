#!/bin/bash

cd prep
bash leap.sh
cd ..

# complex vdw    : 25 windows
# complex elec   : 17 windows
# ligand vdw     : 11 windows
# ligand elec    : 11 windows
# Total schedule : 64 windows
lambda1=(0.0 0.01592 0.08198 0.19331 0.33787 0.5 0.66213 0.80669 0.91802 0.98408 1.0) # 11 windows
lambda2=(0.00000 0.00600 0.03136 0.07590 0.13779 0.21451 0.30292 0.39940 0.50000 0.60060 0.69708 0.78549 0.86221 0.92410 0.96864 0.99400 1.00000) # 17 windows
lambda3=(0.0 0.00262 0.01373 0.03351 0.06162 0.09756 0.14067 0.19020 0.24525 0.30485 0.36793 0.43337 0.50000 0.56663 0.63207 0.69515 0.75475 0.80980 0.85933 0.90244 0.93838 0.96649 0.98627 0.99738 1.00000) # 25 windows
mbar_list1=`echo ${lambda1[@]} | sed "1,$ s/ /, /g"` ; mbar_num1=`echo ${#lambda1[@]}`
mbar_list2=`echo ${lambda2[@]} | sed "1,$ s/ /, /g"` ; mbar_num2=`echo ${#lambda2[@]}`
mbar_list3=`echo ${lambda3[@]} | sed "1,$ s/ /, /g"` ; mbar_num3=`echo ${#lambda3[@]}`

let n_res=`cat prep/prot.pdb | grep CA | wc -l`
let n_term=n_res+1 ; let n_lig=n_res+2


cdir=`pwd`
echo -n "" > list
# complex vdw
for ((j=0; j<${#lambda3[@]}; j++))
do
    mkdir -p v${j}
    cat amber_files/qsub.sh | sed "1,$ s/NAME/ti_v${j}/g" > v${j}/qsub.sh
    cp amber_files/run.sh v${j}/
    cv_num=`cat prep/complex/GB.pdb | grep "ATOM" | grep -v "LIG" | 
      awk 'BEGIN { num=0 } { if ( $3=="C" || $3=="O" || $3=="CA" || $3=="N" ) num+=1 } END {print num+2}'`
    cv_atoms=`cat prep/complex/GB.pdb | grep "ATOM" | grep -v "LIG" |
      awk 'BEGIN { printf "1,0," } { if ( $3=="C" || $3=="O" || $3=="CA" || $3=="N") printf "%s,", $2}'`
    let resnum=n_res+2
    cat amber_files/cv.in | sed "1,$ s/CV_NUM/${cv_num}/g;s/ATOM_NUM/${cv_atoms}/g" > v${j}/cv.in
    cat amber_files/heat-lj-comp.in | sed "1,$ s/C_LAMBDA/${lambda3[$j]}/g;s/MK1/${n_lig}/g;s/RESNUM/${n_term}/g" > v${j}/heat.in
    cat amber_files/eq-lj-comp.in | sed "1,$ s/C_LAMBDA/${lambda3[$j]}/g;s/MK1/${n_lig}/g;s/RESNUM/${n_term}/g" > v${j}/eq.in
    cat amber_files/ti-lj-comp.in | sed "1,$ s/C_LAMBDA/${lambda3[$j]}/g;s/MK1/${n_lig}/g;s/MBAR_NUM/${mbar_num3}/g;s/MBAR_LIST/${mbar_list3}/g;s/RESNUM/${n_term}/g" > v${j}/ti.in
    ln -s ${cdir}/prep/complex/wat_decharged.parm7 v${j}/wat.parm7
    ln -s ${cdir}/prep/complex/wat.rst7 v${j}/wat.rst7
    cp ${cdir}/prep/disang.rest v${j}/disang.rest
    echo "v${j}" >> list
done


# complex elec
for ((j=0; j<${#lambda2[@]}; j++))
do
    mkdir -p e${j}
    cat amber_files/qsub.sh | sed "1,$ s/NAME/ti_e${j}/g" > e${j}/qsub.sh
    cp amber_files/run.sh e${j}/
    cv_num=`cat prep/complex/GB.pdb | grep "ATOM" | grep -v "LIG" | 
      awk 'BEGIN { num=0 } { if ( $3=="C" || $3=="O" || $3=="CA" || $3=="N" ) num+=1 } END {print num+2}'`
    cv_atoms=`cat prep/complex/GB.pdb | grep "ATOM" | grep -v "LIG" |
      awk 'BEGIN { printf "1,0," } { if ( $3=="C" || $3=="O" || $3=="CA" || $3=="N") printf "%s,", $2}'`
    let resnum=n_res+3
    cat amber_files/cv.in | sed "1,$ s/CV_NUM/${cv_num}/g;s/ATOM_NUM/${cv_atoms}/g" > e${j}/cv.in
    cat amber_files/heat-ch-comp.in | sed "1,$ s/C_LAMBDA/${lambda2[$j]}/g;s/MK1/${n_lig}/g;s/RESNUM/${n_term}/g" > e${j}/heat.in
    cat amber_files/eq-ch-comp.in | sed "1,$ s/C_LAMBDA/${lambda2[$j]}/g;s/MK1/${n_lig}/g;s/RESNUM/${n_term}/g" > e${j}/eq.in
    cat amber_files/ti-ch-comp.in | sed "1,$ s/C_LAMBDA/${lambda2[$j]}/g;s/MK1/${n_lig}/g;s/MBAR_NUM/${mbar_num2}/g;s/MBAR_LIST/${mbar_list2}/g;s/RESNUM/${n_term}/g"> e${j}/ti.in
    ln -s ${cdir}/prep/complex/wat.parm7 e${j}/wat.parm7
    ln -s ${cdir}/prep/complex/wat.rst7 e${j}/wat.rst7
    cp ${cdir}/prep/disang.rest e${j}/disang.rest
    echo "e${j}" >> list
done


# ligand vdw
for ((j=0; j<${#lambda1[@]}; j++))
do
    mkdir -p w${j}
    cat amber_files/qsub.sh | sed "1,$ s/NAME/ti_w${j}/g" > w${j}/qsub.sh
    cp amber_files/run.sh w${j}/
    let resnum=1
    cat amber_files/heat-lj-lig.in | sed "1,$ s/C_LAMBDA/${lambda1[$j]}/g;s/MK1/1/g" > w${j}/heat.in
    cat amber_files/eq-lj-lig.in | sed "1,$ s/C_LAMBDA/${lambda1[$j]}/g;s/MK1/1/g" > w${j}/eq.in
    cat amber_files/ti-lj-lig.in | sed "1,$ s/C_LAMBDA/${lambda1[$j]}/g;s/MK1/1/g;s/MBAR_NUM/${mbar_num1}/g;s/MBAR_LIST/${mbar_list1}/g" > w${j}/ti.in
    ln -s ${cdir}/prep/lig/wat_decharged.parm7 w${j}/wat.parm7
    ln -s ${cdir}/prep/lig/wat.rst7 w${j}/wat.rst7
    echo "w${j}" >> list
done


#ligand elec
for ((j=0; j<${#lambda1[@]}; j++))
do
    mkdir -p f${j}
    cat amber_files/qsub.sh | sed "1,$ s/NAME/ti_f${j}/g" > f${j}/qsub.sh
    cp amber_files/run.sh f${j}/
    let resnum=1
    cat amber_files/heat-ch-lig.in | sed "1,$ s/C_LAMBDA/${lambda1[$j]}/g;s/MK1/1/g" > f${j}/heat.in
    cat amber_files/eq-ch-lig.in | sed "1,$ s/C_LAMBDA/${lambda1[$j]}/g;s/MK1/1/g" > f${j}/eq.in
    cat amber_files/ti-ch-lig.in | sed "1,$ s/C_LAMBDA/${lambda1[$j]}/g;s/MK1/1/g;s/MBAR_NUM/${mbar_num1}/g;s/MBAR_LIST/${mbar_list1}/g" > f${j}/ti.in
    ln -s ${cdir}/prep/lig/wat.parm7 f${j}/wat.parm7
    ln -s ${cdir}/prep/lig/wat.rst7 f${j}/wat.rst7
    echo "f${j}" >> list
done


