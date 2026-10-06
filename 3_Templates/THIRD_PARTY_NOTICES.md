# Third-party notices

## REMD temperature predictor

T-REMD, REST2와 REST3 leaf의 `helpers/temperature_ladder.py`는 아래 MIT source의
temperature predictor를 구현합니다. 각 leaf는 독립 사본을 유지합니다.

The leaf-local `helpers/temperature_ladder.py` copies in T-REMD, REST2,
and REST3 reimplement the algorithm distributed by the
`remd-temperature-generator` project:

- Patriksson, A.; van der Spoel, D. *A temperature predictor for parallel
  tempering simulations*. Phys. Chem. Chem. Phys. 2008, 10, 2073–2077.
- Source: <https://github.com/dspoel/remd-temperature-generator>
- Original source license: MIT

The empirical model was calibrated for OPLS/AA and GROMACS temperature REMD.
Generated temperatures are initial estimates and require pilot-run validation.
