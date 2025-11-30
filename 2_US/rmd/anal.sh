#!/bin/bash

anal="parm wat.parm7\n
trajin rmd/rmd.nc\n
distance @1 @132 out anal/dist.dat\n
run"

mkdir -p anal
echo -e $anal > anal.in
cpptraj -i anal.in
rm anal.in
