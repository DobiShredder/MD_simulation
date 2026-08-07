# REST2

## 한국어

Chignolin을 ff19SB/TIP3P로 만들고 8-replica REST2를 실행합니다. Protein
Hamiltonian만 300–500 K effective temperature에 맞춰 scaling하며 실제 bath
temperature는 300 K입니다. Equilibration은 1 ns, production은 replica당
10 ns이고 교환은 2 ps마다 시도합니다.

### 실행

AMBER 26, ParmEd, GROMACS 2026.3, PLUMED 2.10과 HREX를 지원하도록 PLUMED
patch가 적용된 MPI GROMACS가 필요합니다. `partial_tempering`은 `gawk`도
사용합니다.

```bash
python3 -m pip install -r requirements.txt
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

`build.sh`는 AMBER topology를 ParmEd로 GROMACS 형식으로 바꾼 뒤 protein
atom type에만 `_` marker를 붙입니다. PLUMED `partial_tempering`으로
8개 topology를 만들고, scale 1.0 topology와 원본 topology의 potential
energy를 한 frame rerun으로 비교합니다. 허용 오차는
`ENERGY_TOLERANCE_KJ_MOL`로 바꿀 수 있습니다.

`GROMACS`, `GROMACS_MPI`, `MPI_LAUNCHER`, `MPI_PROCESSES`,
`MPI_OPTIONS`와 `GROMACS_OPTIONS`로 실행 환경을 지정합니다. Production은
10개의 1 ns segment이며 일부 replica만 완료된 segment에서는 resume하지
않습니다.

### Output

- `work/replicas/NNN/topol.top`
- `work/replicas/NNN/production.001.xtc` … `production.010.xtc`
- `work/exchange_summary.tsv`, `replica_visits.tsv`,
  `state_occupancy.tsv`
- `work/structure_by_temperature.tsv`: Rg와 residue 1–10 CA distance

REST2의 높은 effective temperature에서 나타나는 compaction은 mini-protein
folding sampling을 돕기 위해 사용되어 온 method 특성입니다. 짧은 Chignolin
계산만으로 force field 성능이나 수렴을 판단하지 않습니다.

## English

This example runs eight-state REST2 for ff19SB/TIP3P Chignolin. Only protein
interactions are scaled over effective temperatures of 300–500 K; the physical
bath remains at 300 K. Equilibration is 1 ns, production is ten 1 ns segments,
and exchanges are attempted every 2 ps.

The build converts the AMBER system with ParmEd, marks only protein atom types,
creates scaled topologies with PLUMED `partial_tempering`, and compares the
scale-one and original potential energies. A PLUMED-patched MPI GROMACS build
with HREX support is required.

The analysis writes exchange acceptance, state visits, occupancy, radius of
gyration, and terminal Cα distance as TSV files. High-temperature compaction
in REST2 has been used intentionally to assist mini-protein folding sampling;
this short example does not establish convergence or force-field quality.

