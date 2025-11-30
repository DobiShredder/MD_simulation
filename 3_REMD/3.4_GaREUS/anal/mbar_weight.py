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
cv_file = np.loadtxt('../dist.dat')
dist_T = np.loadtxt('t/dist.dat.1', dtype='str')[180000::45]

min1 = cv_file[0,0]-0.5
max1 = cv_file[-1,0]+1
nrep = int(np.size(cv_file[:,0]))
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
filename = '../dist.dat'
lines = np.loadtxt(filename)
for k in range(nrep):
    line = lines[k]
    dist0_k[k] = float(line[0])
    K_k[k] = 2 * float(line[1]) * cal2j
    if len(line) > 2:
        T_k[k] = float(line[2])

for k in range(nrep):
    j = k+1
    filename = 't/dist.dat.%d' % j
    print("Reading %s..." % filename)
    temp = np.float64(np.loadtxt(filename, dtype='str')[:,7][180000::45])
    lines = np.column_stack( [ np.where(temp.T)[0], temp.T ] )

    n=0
    for line in lines:
       a = float(line[1])
       dist_kn[k, n] = a
       n += 1
       N_k[k] = n
       #g_k[k] = timeseries.statisticalInefficiency(dist_kn[k, 0:N_k[k]])
       #indices = timeseries.subsampleCorrelatedData(dist_kn[k, 0:N_k[k]], g=g_k[k])

       #N_k[k] = len(indices)
       #u_kn[k, 0:N_k[k]] = u_kn[k, indices]
       #dist_kn[k, 0:N_k[k]] = dist_kn[k, indices]
cv_dist = np.hstack( [ (np.where(dist_kn[n,:])[0]+1, dist_kn[n,:]) for n in range(nrep) ] ).T

plt.figure(figsize=(12,9))
for i in range(nrep):
    plt.hist(dist_kn[i], bins=100)
plt.show()


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


print("PMF (in units of kT)")
print("%8s %8s %8s" % ('bin', 'f', 'df'))
for i in range(nbins):
    #print("%8.1f %8.3f %8.3f" % (bin_center_i[i], f_i[i] * R * T / 4.184, df_i[i]))
    print("%8.1f %8.3f %8.3f" % (bin_center_i[i], f_i[i], df_i[i]))

# Compute weights in unbiased potential
if len(np.shape(u_kn)) == 2:
    u_n = kn_to_n(u_kn, N_k = mbar.N_k)
else:
    u_n = u_kn
log_w_n = mbar._computeUnnormalizedLogWeights(u_n)
weight = np.exp(log_w_n)/np.exp(logsumexp(log_w_n))

# Write out weights
f = open('weights.dat', 'w')
for k in range(nrep):
    for i in range(k*N_max, (k+1)*N_max):
        f.write('{}    {:.15E}\n'.format(i+1-k*N_max, weight[i]))
f.close()

weights_file = 'weights.dat'

nbin_max = 1000000
fe_max = 10000000.0
cutoff = float(10)


# GAMD Potentail energy reading
gamd_T = np.concatenate( [ np.loadtxt('../gamd/gamd.log.%d' % (i+1))[19799:-1] for i in range(nrep) ] )
gamd_out = np.column_stack( [ gamd_T[:,1], gamd_T[:,6], gamd_T[:,7] ] )

boosts = np.zeros(nsample*nrep, float)

j = 0
for line in gamd_out:
    a = line
    pot = float(a[1])
    dih = float(a[2])
    boosts[j] = pot + dih
    j += 1

weights = np.ones(nsample * nrep, float)

if os.path.isfile(weights_file):
    j = 0
    for line in open (weights_file):
        a = line.split()
        weights[j] = float(a[1])
        j += 1

bin_center_i = np.zeros(nbins, float)
nsample_in_bin = np.zeros(nbins, int)
weights_in_bin = np.zeros(nbins, float)
avg = np.zeros(nbins, float)
avg2 = np.zeros(nbins, float)
j = 0

for i in range(nbins):
    bin_center_i[i] = min1 + delta/2 + delta * i

for line in cv_dist:
    a = line
                    
    cv1 = float(a[1])
    idx1 = int( (cv1 - min1) / delta )
                                
    if 0 <= idx1 < nbins:
        nsample_in_bin[idx1] += 1
        weights_in_bin[idx1] += weights[j]
        avg[idx1] += weights[j] * boosts[j]
        avg2[idx1] += weights[j] * boosts[j]**2
        j += 1

fe = np.zeros(nbins, float)
fe_noreweight = np.zeros(nbins, float)
fe_min = fe_max

for i in range(nbins):
    if nsample_in_bin[i] == 0:
        fe[i] = fe_max
    else:
        if nsample_in_bin[i] > cutoff:
            c1 = beta * avg[i] / weights_in_bin[i]
            c2 = 0.5 * beta**2 * (avg2[i] / weights_in_bin[i] - (avg[i] / weights_in_bin[i])**2 )
            fe_noreweight[i] = - R * T / cal2j * np.log(weights_in_bin[i])
            fe[i] = - R * T / cal2j * (c1 + c2) + fe_noreweight[i]
        if fe[i] < fe_min:
            fe_min = fe[i]
fe -= fe_min

for i in range(nbins):
    print("%8.1f %8.3f" % (bin_center_i[i], fe[i]))

f = open('result.dat', 'w')
for i in range(nbins):
    f.write('{:2.2f}    {:2.8f}\n'.format(bin_center_i[i], fe[i]))
f.close()

#plt.figure(figsize=(12,9))
#plt.xticks(fontsize=20)
#plt.yticks(fontsize=20)
#plt.xlabel('Distance (Å)', fontsize=30)
#plt.ylabel('PMF (kcal/mol)', fontsize=30)
#plt.plot(bin_center_i, fe)
#plt.show()
