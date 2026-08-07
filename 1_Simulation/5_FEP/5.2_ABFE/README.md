# Absolute binding free energy with AMBER / AMBER ABFE

Reference syntax: Amber 2026 thermodynamic integration, soft-core potentials,
MBAR energy collection, and NMR-style restraints.

## 한국어

Double decoupling으로 ligand의 electrostatic과 Lennard-Jones interaction을
complex/solvent leg에서 제거합니다. Complex equilibration 뒤
ligand–receptor distance, angle과 dihedral restraint를 만듭니다.

1. [equil/](equil/README.md)에서 complex 준비와 equilibration
2. 생성된 protein/ligand 구조를 dd/prep에 전달
3. [dd/](dd/README.md)에서 restraint와 64개 window 생성
4. 각 window의 run.sh 또는 dd/run_all.sh 실행
5. MBAR 또는 지원되는 estimator로 window 결과 분석

Atom/residue 번호, anchor atom, ligand parameter, lambda schedule과 production
length는 example 값입니다. ABFE 계산에는 window overlap, restraint
stability, standard-state correction과 독립 반복 결과가 필요합니다.

## English

This double-decoupling template equilibrates a complex, constructs six
ligand–receptor restraints, and decouples electrostatics and Lennard-Jones
interactions in complex and solvent legs. A complete ABFE cycle also requires
validated restraint and standard-state corrections.

Follow `equil/`, transfer the structures to `dd/prep`, generate 64 windows, and
run each window. An ABFE estimator is not included yet. Adapt atom selections,
anchors, parameters, schedules, and lengths; report overlap, restraint
stability, corrections, and repeats.
