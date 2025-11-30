#!/usr/env python3

import argparse
import numpy as np
from pymol import cmd

parser = argparse.ArgumentParser(description='Move COM of protein to zero point',
                                 usage='use "python3 com.py -i input.pdb -o output.pdb"')
parser.add_argument('-i', '--input', required=True, help='Input PDB File Name')
parser.add_argument('-o', '--output', default='aligned.pdb', help='Output PDB File Name (default : aligned.pdb)')

args = parser.parse_args()

input_name = args.input
output_name = args.output


coord = np.array([], dtype=float)
mass_sum = 0
weighted_sum = [0, 0, 0]

with open(input_name) as f:
    for lines in f:
        if lines.startswith('ATOM'):
            line = lines.strip().split()
            xyz = [ float(x) for x in line[5:8] ]
            if list(line[2])[0] == 'C':
                mass = float(12.011)
            elif list(line[2]) == 'N':
                mass = float(14.006)
            elif list(line[2]) == 'O':
                mass = float(15.999)
            elif list(line[2]) == 'H':
                mass = float(1.008)
            else:
                mass = float(12.011)
            mass_sum += mass
            weighted_sum[0] += xyz[0] * mass
            weighted_sum[1] += xyz[1] * mass
            weighted_sum[2] += xyz[2] * mass

center_of_mass = [ -x / mass_sum for x in weighted_sum ]

cmd.load(filename=input_name, object='complex')
cmd.translate(vector=center_of_mass, selection='complex', camera=0)
cmd.save(filename=output_name, selection='complex')


