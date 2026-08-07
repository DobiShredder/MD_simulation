#/usr/env python3

import argparse
import numpy as np

parser = argparse.ArgumentParser(description='TI lambda points and weights generator based on Gaussian quadrature',
                                 usage='use "python3 ti.py -p 5"')
parser.add_argument('-p', '--n_point', metavar='POINT', required=True,
                    help='Number of lambda Points in Thermodynamics Integration (TI)')

args = parser.parse_args()
nlambda = int(args.n_point)-2



np.set_printoptions(formatter={'float': '{: 0.5f}'.format})
t = np.polynomial.legendre.leggauss(nlambda)
t1 = np.array([0])
t2 = np.array([1])

points = (t[0] + 1) / 2
weight = t[1] / 2
weights = weight.tolist()
lambdas = np.concatenate([t1, points, t2]).tolist()

print("Lambdas          :", " ".join("{:.5f}".format(i) for i in lambdas))
print("Gaussian weights :", " ".join("{:.5f}".format(i) for i in weights))
#print("lambdas          :", *lambdas, sep=' ')
#print("Gaussian weights :", *weights, sep=' ')
