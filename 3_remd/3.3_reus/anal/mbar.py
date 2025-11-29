import sys, math, os
import numpy as np
import pymbar
import matplotlib.pyplot as plt
from pymbar import timeseries
from pymbar.utils import kn_to_n, logsumexp

# constants
R = 8.31446261815324 / 1000.0 # gas constant, kJ K-1 mol-1
T = float(300)
cal2j = float(4.1841)
beta = 1.0 / (R * T)

#parameters setup
cv_file = np.loadtxt('../../../dist.dat')
dist_T = np.loadtxt('../1/dist/dist.dat', dtype='str')[50000:]

min1 = cv_file[0]-0.5
max1 = cv_file[-1]+1
nrep = int(np.size(cv_file))
nsample = int(np.size(dist_T[:,0]))
T_k = np.ones(nrep, float) * T
fe_max = 10000000.0
beta_k = 1.0/(R * T_k)

delta = 0.25
nbins = int( (max1-min1) / delta )
cutoff = float(10)

N_k = np.zeros([nrep], np.int64)
K_k = np.zeros([nrep], np.float64)
dist0_k = np.zeros([nrep], np.float64)
dist_kn = np.zeros([nrep, nsample], np.float64)
u_kn = np.zeros([nrep, nsample], np.float64)
g_k = np.zeros([nrep], np.float64)


# Read in umbrella spring constants and centers.
filename = '../../../dist.dat'
lines = np.loadtxt(filename)
for k in range(nrep):
    line = lines[k]
    dist0_k[k] = float(line)
    #K_k[k] = 2 * float(line[1]) * cal2j
    K_k[k] = 2 * cal2j
    #if len(line) > 2:
        #T_k[k] = float(line[2])

for k in range(nrep):
    j = k+1
    filename = '../%d/dist/dist.dat' % j
    print("Reading %s..." % filename)
    temp = np.float64(np.loadtxt(filename, dtype='str')[:,7][50000:])
    lines = np.column_stack( [ np.where(temp.T)[0], temp.T ] )

    n=0
    for line in lines:
        a = float(line[1])
        dist_kn[k, n] = a
        n += 1
        N_k[k] = n
cv_dist = np.hstack( [ (np.where(dist_kn[n,:])[0]+1, dist_kn[n,:]) for n in range(nrep) ] ).T

plt.figure(figsize=(12,9))
for i in range(nrep):
    plt.hist(dist_kn[i], bins=100)
plt.savefig('hist.png',dpi=300)

N_max = np.max(N_k)
u_kln = np.zeros([nrep, nrep, N_max], np.float64)
u_kn -= u_kn.min()


print("Binning data...")

bin_center_i = np.zeros([nbins], np.float64)
bin_kn = np.zeros([nrep, nsample], np.int64)

for i in range(nbins):
    bin_center_i[i] = min1 + delta/2 + delta * i

    for k in range(nrep):
        for n in range(N_k[k]):
            bin_kn[k, n] = int((dist_kn[k, n] - min1) / delta)

print("Evaluating reduced potential energies...")

for k in range(nrep):
    for n in range(N_k[k]):
        d_dist = dist_kn[k, n] - dist0_k
        u_kln[k,:,n] = u_kn[k,n] + beta_k[k] * (0.5 * K_k) * d_dist**2


print("Running MBAR...")
mbar = pymbar.MBAR(u_kln, N_k, maximum_iterations=10000, initialize='zeros', verbose = True)

result = mbar.computePMF(u_kn, bin_kn, nbins)
f_i = result[0]
df_i = result[1]

#print("PMF (in units of kT)")
#print("%8s %8s %8s" % ('bin', 'f', 'df'))
#for i in range(nbins):
    #print("%8.1f %8.3f %8.3f" % (bin_center_i[i], f_i[i] * R * T / 4.184, df_i[i]))
    #print("%8.1f %8.3f %8.3f" % (bin_center_i[i], f_i[i], df_i[i]))

f = open('pmf.dat', 'w')
for i in range(nbins):
    f.write('{:2.2f}    {:2.8f}    {:2.8f}\n'.format(bin_center_i[i], f_i[i], df_i[i]))
f.close()


