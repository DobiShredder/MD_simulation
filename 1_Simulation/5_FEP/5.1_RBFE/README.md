# Relative binding free energy with GROMACS / GROMACS RBFE

Reference syntax: GROMACS 2026.3; hybrid topology generation additionally
requires a compatible pmx installation.

## 한국어

pmx hybrid topology로 residue mutation을 만들고 lambda state 21개를
실행합니다. `mut.py`는 residue 4를 alanine으로 바꿉니다.
`prep/prep.sh`의 pmx와 GROMACS 경로는 설치 환경에 맞게 수정합니다.

~~~bash
cd 1_Simulation/5_FEP/5.1_RBFE/prep
# pmx/gmx 경로, mutation, force field를 수정
bash prep.sh
cd ..
bash run.sh
~~~

Mutation, topology mapping, charge change와 thermodynamic cycle은 example
system에 맞게 바꿉니다. `run.sh`의 GPU/MPI 설정과 `nsteps`도 실행 환경에
맞춥니다. `grompp` warning은 원인을 수정합니다. 결과에서는 lambda별
`dH/dlambda` overlap, forward/reverse hysteresis와 cycle closure를 확인합니다.

## English

pmx builds a hybrid topology followed by minimization,
equilibration, and production for 21 lambda states before gmx bar. pmx/gmx
paths and the residue-4-to-alanine mutation are system-specific placeholders.

Adapt the mutation, mapping, force field, MPI/GPU launch, and thermodynamic
cycle before running `prep.sh` and `run.sh`. Resolve all `grompp` warnings. Check
charge corrections, neighboring-state overlap, forward/reverse hysteresis,
independent repeats, and cycle closure.
