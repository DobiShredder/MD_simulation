#!/bin/bash

source ~/bashrc/kbs

### Prn = residue number in receptor
### Ln = atom name in ligand
Prn=( 120 129 149 )
Lan=( 'C2' 'C4' 'C6' )

for i in complex lig
do
    cd $i
    tleap -f leap.src
    parmed -O -i ../decharge.in
    cd ..
done


Pn=()
for i in ${Prn[@]}
do
    t=`cat prot.pdb | grep CA | sed -n ${i}p | awk '{print $2}'`
    an=`echo $t+1 | bc`
    Pn+=($an)
done

R_an=`cat prot.pdb | grep ATOM | wc -l`
L_an=`cat lig.pdb | grep ATOM | wc -l`
Ln=()
for x in ${Lan[@]}
do
    t=`cat lig.pdb | grep -w ${x} | awk '{print $2}'`
    t1=`echo ${t}+${R_an}+1 | bc`
    Ln+=(${t1})
done

anal="parm complex/wat.parm7\n
trajin complex/wat.rst7\n
distance @${Pn[0]} @${Ln[0]} out dist.dat\n
angle @${Ln[0]} @${Pn[0]} @${Pn[1]} out a1.dat\n
angle @${Pn[0]} @${Ln[0]} @${Ln[1]} out a2.dat\n
dihedral @${Pn[2]} @${Pn[1]} @${Pn[0]} @${Ln[0]} out d1.dat\n
dihedral @${Pn[1]} @${Pn[0]} @${Ln[0]} @${Ln[1]} out d2.dat\n
dihedral @${Pn[0]} @${Ln[0]} @${Ln[1]} @${Ln[2]} out d3.dat\n
run"

echo -e $anal > anal.in
cpptraj -i anal.in
rm anal.in

dist=`cat dist.dat | tail -n1 | awk '{print $2}'`
a1=`cat a1.dat | tail -n1 | awk '{print $2}'`
a2=`cat a2.dat | tail -n1 | awk '{print $2}'`
d1=`cat d1.dat | tail -n1 | awk '{print $2}'`
d1a=`echo ${d1}-180 | bc`
d1b=`echo ${d1}+180 | bc`
d2=`cat d2.dat | tail -n1 | awk '{print $2}'`
d2a=`echo ${d2}-180 | bc`
d2b=`echo ${d2}+180 | bc`
d3=`cat d3.dat | tail -n1 | awk '{print $2}'`
d3a=`echo ${d3}-180 | bc`
d3b=`echo ${d3}+180 | bc`

rm dist.dat a1.dat a2.dat d1.dat d2.dat d3.dat

rest="&rst iat=${Pn[0]}, ${Ln[0]}, r1=0.000, r2=${dist}, r3=${dist}, r4=999.000, rk2=10.000, rk3=10.000, &end
&rst iat=${Ln[0]}, ${Pn[0]}, ${Pn[1]}, r1=0.000, r2=${a1}, r3=${a1}, r4=180.000, rk2=10.000, rk3=10.000, &end
&rst iat=${Pn[0]}, ${Ln[0]}, ${Ln[1]}, r1=0.000, r2=${a2}, r3=${a2}, r4=180.000, rk2=10.000, rk3=10.000, &end
&rst iat=${Pn[2]}, ${Pn[1]}, ${Pn[0]}, ${Ln[0]}, r1=${d1a}, r2=${d1}, r3=${d1}, r4=${d1b}, rk2=10.000, rk3=10.000, &end
&rst iat=${Pn[1]}, ${Pn[0]}, ${Ln[0]}, ${Ln[1]}, r1=${d2a}, r2=${d2}, r3=${d2}, r4=${d2b}, rk2=10.000, rk3=10.000, &end
&rst iat=${Pn[0]}, ${Ln[0]}, ${Ln[1]}, ${Ln[2]}, r1=${d3a}, r2=${d3}, r3=${d3}, r4=${d3b}, rk2=10.000, rk3=10.000, &end"
printf "${rest}\n" > disang.rest

