#!/usr/env python3
import sys
from glob import glob
import math
import re
import pandas as pd
import alchemlyb
from alchemlyb.parsing.amber import extract_u_nk
from alchemlyb.preprocessing.subsampling import decorrelate_u_nk
from alchemlyb.estimators import MBAR

R_kcal = 1.987204259e-3             # Gas constant in kcal/(mol*K)
T = 300.0                           # Temperature in Kelvin
RT = R_kcal * T                     # kcal/mol
V = 1660.53907                      # standard volume in nm^3

abfe = []
cycle_name = ['comp_charge', 'comp_vdw', 'lig_vdw', 'lig_charge']
data_list = {}

data_list[cycle_name[0]] = glob('e*/ti.out')
data_list[cycle_name[1]] = glob('v*/ti.out')
data_list[cycle_name[2]] = glob('f*/ti.out')
data_list[cycle_name[3]] = glob('w*/ti.out')

for cy in cycle_name:
    u_nk_list = [extract_u_nk(mdout, T=T) for mdout in data_list[cy]]
    decorrelated_u_nk_list = [decorrelate_u_nk(u_nk) for u_nk in u_nk_list]

    mbar = MBAR()
    mbar.fit(alchemlyb.concat(decorrelated_u_nk_list))
    delta_f_kBT = mbar.deltaf_.loc[0.00, 1.00]
    abfe.append(delta_f_kBT * RT)


disang = []                         # disang : dist, a1, a2, d1, d2, d3
rk = []                             # rk : force constant for dist, a1, a2, d1, d2, d3

with open("dd/prep/disang.rest") as f:
    lines = f.readlines()
    for line in lines:
        sub1 = "r2"
        dis_text = list(filter(lambda x: sub1 in x, line.split()))
        sub2 = "rk2"
        rk_text = list(filter(lambda x: sub2 in x, line.split()))

        val_r = float(re.findall("\d+\.\d+", dis_text[0])[0])
        val_k = float(re.findall("\d+\.\d+", rk_text[0])[0])
        disang.append(val_r))
        rk.append(val_k * 2)

thA = math.radians(disang[1])       # convert angle from degrees to radians --> math.sin() wants radians
thB = math.radians(disang[2])       # convert angle from degrees to radians --> math.sin() wants radians


arg =( (8 * math.pi**2 * V) / ((disang[0]/10)**2 * math.sin(thA) * math.sin(thB)) 
      * ( ( (rk[0] * rk[1] * rk[2] * rk[3] * rk[4] * rk[5])**0.5 ) / ( (2 * math.pi * K * T)**(3) ) ) )
dG_rest= - (K * T * math.log(arg)) / 4.184

dG = - abfe[0] - abfe[1] + abfe[2] + abfe[3] + dG_rest

print("complex elec : %.4f" % (-abfe[0]) )
print("complex vdw  : %.4f" % (-abfe[1]) )
print("ligand elec  : %.4f" % abfe[2] )
print("ligand vdw   : %.4f" % abfe[3] )
print("restraint    : %.4f" % (-dG_rest) )
print("dG = %.4f" % dG)

with open('mbar.log', 'w') as f:
    f.write("complex elec : %.4f\n" % (-abfe[0]) )
    f.write("complex vdw  : %.4f\n" % (-abfe[1]) )
    f.write("ligand elec  : %.4f\n" % abfe[2] )
    f.write("ligand vdw   : %.4f\n" % abfe[3] )
    f.write("restraint    : %.4f\n" % (-dG_rest) )
    f.write("dG = %.4f\n" % dG)

