#!/usr/env python3

import argparse
import numpy as np
import MDAnalysis as mda
import warnings

warnings.filterwarnings('ignore')

parser = argparse.ArgumentParser(description='Move COM of protein to origin point',
                                 usage='use "python3 com.py -i input.pdb -o output.pdb"')
parser.add_argument('-i', '--input', required=True, help='Input PDB File Name')
parser.add_argument('-o', '--output', default='aligned.pdb', help='Output PDB File Name (default : aligned.pdb)')

args = parser.parse_args()

input_file = args.input
output_file = args.output


mol = mda.Universe(input_file)

com = mol.atoms.center_of_mass()
print(f"  original COM: {com[0]:.3f} {com[1]:.3f} {com[2]:.3f}")

mol.atoms.translate(-com)
com_moved = mol.atoms.center_of_mass()
mol.atoms.write(output_file)
print(f"translated COM: {com_moved[0]:.3f} {com_moved[1]:.3f} {com_moved[2]:.3f}")

