# Ligand GaMD 3 / LiGaMD3

Reference syntax: Amber 2026 LiGaMD3. This method requires pmemd.cuda support.

## 한국어

Input은 `igamd=28` LiGaMD3 triple boost입니다. Ligand, protein과 나머지
system의 energy term을 나눕니다. `timask1/scmask1=':1'`과
`bgpro2atm=BEGIN`, `edpro2atm=END`는 실제 ligand residue와 protein atom
범위로 바꿉니다.

~~~bash
cd 1_Simulation/4_GaMD/4.2_LiGaMD
# wat.parm7/wat.rst7 준비 후 BEGIN/END와 mask 수정
bash run.sh
~~~

`ligamd-eq.in`은 `irest_gamd=0`으로 boost 통계를 만들고 `ligamd.in`은
`irest_gamd=1`로 이어받습니다. 기본 production은 200 ns × 5회입니다.
Test에서는 길이를 줄이고 ligand residue, soft-core/TI mask, protein atom
범위와 세 boost distribution을 확인합니다.

## English

Despite the folder name, the current inputs implement LiGaMD3 with igamd=28
and three boost components. Replace residue-1 ligand masks and BEGIN/END protein
atom placeholders before running. ligamd-eq.in initializes boost statistics;
ligamd.in continues them with irest_gamd=1.

The script requests five 200 ns production parts. Use a much shorter validation
run first and check TI/soft-core masks, all boost distributions, binding and
unbinding events, restart state, reweighting, and kinetic convergence.
