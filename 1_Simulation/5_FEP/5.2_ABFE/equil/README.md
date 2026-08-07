# ABFE complex equilibration

## 한국어

`prep/com.py`로 complex를 정렬하고 protein/ligand를 분리합니다. tleap은
dummy atom이 포함된 solvated topology를 만듭니다. `nowat.pdb`, ligand
parameter와 residue numbering은 example system에 맞게 수정합니다.

~~~bash
cd 1_Simulation/5_FEP/5.2_ABFE/equil
bash prep.sh
bash run-eq.sh
~~~

`run-eq.sh`는 minimization, heating과 equilibration segment 5개를 실행한 뒤
`split.in`으로 DD input을 만듭니다. Restraint mask, dummy atom, density,
ligand pose와 restart를 확인합니다. 기본 engine은 `pmemd.cuda`입니다.

## English

com.py aligns the complex, preparation separates protein and ligand, and tleap
builds the solvated topology with dummy atoms. Adapt nowat.pdb,
ligand parameters, and residue numbering before prep.sh. run-eq.sh performs
minimization, heating, five equilibration segments, and final splitting.
Check restraints, dummy atoms, density, pose stability, and restarts. The
default engine is pmemd.cuda and can be changed with AMBER_ENGINE.
