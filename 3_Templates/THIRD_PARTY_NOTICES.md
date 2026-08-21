# Third-party notices

## REMD temperature predictor

`common/temperature_ladder.py` reimplements the algorithm distributed by the
`remd-temperature-generator` project:

- Patriksson, A.; van der Spoel, D. *A temperature predictor for parallel
  tempering simulations*. Phys. Chem. Chem. Phys. 2008, 10, 2073–2077.
- Source: <https://github.com/dspoel/remd-temperature-generator>
- Original source license: MIT

The empirical model was calibrated for OPLS/AA and GROMACS temperature REMD.
Generated temperatures are initial estimates and require pilot-run validation.
