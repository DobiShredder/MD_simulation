#!/bin/bash

anal="parm ../wat.parm7\n
trajin rmd/rmd.nc\n
distance @1 @132 out dist.dat\n
run"

echo -e $anal > anal.in
cpptraj -i anal.in

