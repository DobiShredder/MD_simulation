#!/usr/env python3
import sys
from glob import glob
import math
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

import alchemlyb
from alchemlyb.parsing.amber import extract_u_nk
from alchemlyb.preprocessing.subsampling import decorrelate_u_nk
from alchemlyb.estimators import MBAR


R_kcal = 1.987204259e-3             # Gas constant in kcal/(mol*K)
T = 300.0                           # Temperature in Kelvin
RT = R_kcal * T                     # kcal/mol
V = 1660.53907                      # standard volume in nm^3

def plot_overlap_matrix(ax, matrix, title):
    n_rows, n_cols = matrix.shape
    im = ax.imshow(matrix, cmap='Greys', vmin=0.0, vmax=1.0, origin='upper')

    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')

    ticks = np.arange(n_cols)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(ticks, fontsize=10, fontweight='bold')
    ax.set_yticklabels(ticks, fontsize=10, fontweight='bold')

    ax.set_xlabel(r"$\lambda$ Index", fontsize=12, labelpad=2)
    ax.set_ylabel("State Index", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold', y=1.08)
    ax.set_xticks(np.arange(n_cols + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n_rows + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="gray", linestyle='-', linewidth=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    for i in range(n_rows):
        for j in range(n_cols):
            val = matrix[i, j]
            text_color = "white" if val > 0.5 else "black"

            if val >= 0.01:
                text_str = f"{val:.2f}".lstrip('0') if val < 1 else "1.0"
                ax.text(j, i, text_str, ha="center", va="center",
                        color=text_color, fontsize=9, fontweight='bold')

            if val > 0.03 and abs(i - j) <= 1:
                rect = patches.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                         linewidth=2, edgecolor='black', facecolor='none')
                ax.add_patch(rect)

    for k in range(n_rows - 1):
        if matrix[k, k+1] < 0.05:
             rect = patches.Rectangle((k + 0.5, k - 0.5), 1, 1,
                                      linewidth=2.5, edgecolor='red', facecolor='none', zorder=10)
             ax.add_patch(rect)


abfe = []
cycle_name = ['comp_charge', 'comp_vdw', 'lig_vdw', 'lig_charge']
titles = ['Complex: decharge', 'Complex: decouple vdW', 'Ligand: decouple vdW', 'Ligand: decharge']
data_list = {}

data_list[cycle_name[0]] = glob('e*/ti.out')
data_list[cycle_name[1]] = glob('v*/ti.out')
data_list[cycle_name[2]] = glob('f*/ti.out')
data_list[cycle_name[3]] = glob('w*/ti.out')

fig, axes = plt.subplots(2, 2, figsize=(12, 12))
axes_flat = axes.flatten()

for i, cy in enumerate(cycle_name):
    u_nk_list = [extract_u_nk(mdout, T=T) for mdout in data_list[cy]]
    decorrelated_u_nk_list = [decorrelate_u_nk(u_nk) for u_nk in u_nk_list]

    mbar = MBAR()
    mbar.fit(alchemlyb.concat(decorrelated_u_nk_list))
    delta_f_kBT = mbar.delta_f_.loc[0.00, 1.00]
    abfe.append(delta_f_kBT * RT)

    ax = axes_flat[i]
    overlap_results =  mbar._mbar.compute_overlap()
    overlap_matrix = overlap_results['matrix']
    plot_overlap_matrix(ax, overlap_matrix, titles[i])


# calculate restraint energy
disang = []                         # disang : dist, a1, a2, d1, d2, d3
rk = []                             # rk : force constant for dist, a1, a2, d1, d2, d3

with open("prep/disang.rest") as f:
    lines = f.readlines()
    for line in lines:
        sub1 = "r2"
        dis_text = list(filter(lambda x: sub1 in x, line.split()))
        sub2 = "rk2"
        rk_text = list(filter(lambda x: sub2 in x, line.split()))

        val_r = float(re.findall("\d+\.\d+", dis_text[0])[0])
        val_k = float(re.findall("\d+\.\d+", rk_text[0])[0])
        disang.append(val_r)
        rk.append(val_k * 2)

thA = math.radians(disang[1])       # convert angle from degrees to radians --> math.sin() wants radians
thB = math.radians(disang[2])       # convert angle from degrees to radians --> math.sin() wants radians


arg =( (8 * math.pi**2 * V) / ((disang[0]/10)**2 * math.sin(thA) * math.sin(thB)) 
      * ( ( (rk[0] * rk[1] * rk[2] * rk[3] * rk[4] * rk[5])**0.5 ) / ( (2 * math.pi * RT)**(3) ) ) )
dG_rest= - RT * math.log(arg)


# Total results
dG = - abfe[0] - abfe[1] + abfe[2] + abfe[3] - dG_rest

print("complex elec : %.4f" % (-abfe[0]) )
print("complex vdw  : %.4f" % (-abfe[1]) )
print("ligand elec  : %.4f" % abfe[2] )
print("ligand vdw   : %.4f" % abfe[3] )
print("restraint    : %.4f" % (-dG_rest) )
print("dG = %.4f" % dG)

with open('mbar_result.log', 'w') as f:
    f.write("complex elec : %.4f\n" % (-abfe[0]) )
    f.write("complex vdw  : %.4f\n" % (-abfe[1]) )
    f.write("ligand elec  : %.4f\n" % abfe[2] )
    f.write("ligand vdw   : %.4f\n" % abfe[3] )
    f.write("restraint    : %.4f\n" % (-dG_rest) )
    f.write("dG = %.4f\n" % dG)

# visualize overlap matrix
plt.tight_layout()
plt.suptitle('MBAR overlap matrix for FEP cycles', fontsize=20, y=1.02)
plot_filename = 'mbar_overlap_matrix.png'
plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
plt.show()

