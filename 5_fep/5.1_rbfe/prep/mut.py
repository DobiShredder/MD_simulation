from pmx import *

m = Model('1uao.pdb', rename_atoms=True)
m2 = mutate(m=m, mut_resid=4, mut_resname='A', ff='amber99sb-star-ildn-mut')
m2.write('mutant.pdb')
