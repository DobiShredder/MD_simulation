# ABFE double decoupling windows / ABFE DD window

## 한국어

`prep/leap.sh`의 receptor anchor `Prn`과 ligand anchor `Lan`을 수정합니다.
`prep.sh`는 complex LJ 25개, complex charge 17개, solvent LJ 11개와 solvent
charge 11개 window를 생성합니다.

~~~bash
cd 1_Simulation/5_FEP/5.2_ABFE/dd
bash prep.sh
# 먼저 window 하나를 짧게 검증
(cd v0 && bash run.sh)
# 전체 실행은 자원과 수렴 계획을 확인한 뒤 수행
bash run_all.sh
~~~

Scheduler script는 포함하지 않습니다. `clambda`, soft-core/TI mask,
restraint atom과 MBAR lambda list는 생성된 topology에 맞아야 합니다.
Window별 `ti.out`, trajectory와 MBAR energy를 확인합니다.

## English

Replace receptor anchor residues Prn and ligand atoms Lan in prep/leap.sh.
prep.sh generates 25 complex-LJ, 17 complex-charge, 11 solvent-LJ, and 11
solvent-charge windows plus list. Test one shortened window before run_all.sh.

No qsub.sh files are supplied; create an external scheduler adapter if needed.
Check `clambda` values, soft-core/TI masks, restraint atom indices, MBAR lists,
and topology correspondence for every leg and window.
