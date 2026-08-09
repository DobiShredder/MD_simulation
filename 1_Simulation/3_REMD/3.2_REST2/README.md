# REST2

## 한국어

Chignolin을 ff19SB/TIP3P로 만들고 8-replica REST2를 실행합니다. Protein
Hamiltonian만 300–500 K effective temperature에 맞춰 scaling하며 실제 bath
temperature는 300 K입니다. Equilibration은 100 ps, production은 replica당
1 ns이고 교환은 2 ps마다 시도합니다.

REST2는 전체 solvent를 실제로 가열하지 않고 solute–solute interaction을
`λ=T0/Tm`, solute–solvent interaction을 `sqrt(λ)`로 scaling합니다. Solvent–
solvent interaction은 그대로 유지하므로 T-REMD보다 적은 replica로 solute의
effective-temperature ladder를 구성할 수 있습니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 1UAO의 첫 NMR model을 simulation PDB로 정리합니다. |
| `convert_topology.py` | Tleap의 AMBER topology를 GROMACS 형식으로 변환합니다. |
| `mark_hot.py` | Protein atom type에만 `partial_tempering` marker를 붙입니다. |
| `build.sh` | 변환·scaling을 호출해 8개 topology/TPR를 만들고 scale-one energy를 검사합니다. |
| `compare_energy.py` | 원본과 scale 1.0 rerun potential 차이를 허용 오차와 비교합니다. |
| `run.sh` | 300 K pre-production과 PLUMED-patched GROMACS HREX를 실행합니다. |
| `anal.py` | Exchange, occupancy와 effective-temperature별 구조 지표를 계산합니다. |

### 실행

AMBER 26, ParmEd, GROMACS 2026.3, PLUMED 2.10과 HREX를 지원하도록 PLUMED
patch가 적용된 MPI GROMACS가 필요합니다. `partial_tempering`은 `gawk`도
사용합니다.

PLUMED 2.10의 공식 patch 대상 목록에는 GROMACS 2026.3이 포함되어 있지
않습니다. Version 번호만으로 호환된다고 판단하지 않으며, `run.sh`가 실제
`gmx_mpi mdrun -h`에서 `-hrex`와 `-plumed`를 모두 확인합니다.

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
1 ns segment 하나이며 일부 replica만 완료된 segment에서는 resume하지
않습니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `states.tsv`의 `effective_temperature_K` | 300–500 K ladder와 topology scaling factor를 정의합니다. Bath temperature는 아닙니다. |
| Protein `_` marker | `partial_tempering`이 scaling할 hot region을 protein atom으로 제한합니다. |
| `ref-t=300` | 모든 replica의 physical thermostat temperature입니다. |
| `-multidir`, `-replex 1000` | 8개 directory를 HREX로 묶고 1,000 steps, 즉 2 ps마다 교환합니다. |
| `constraints=h-bonds`, `dt=0.002` | LINCS로 수소 bond를 고정하고 2 fs timestep을 사용합니다. |
| `ENERGY_TOLERANCE_KJ_MOL` | Scale 1.0 topology identity의 one-frame potential 허용 오차입니다. |

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
bath remains at 300 K. Equilibration is 100 ps, production is one 1 ns segment,
and exchanges are attempted every 2 ps.

REST2 scales solute–solute interactions by `lambda=T0/Tm` and solute–solvent
interactions by `sqrt(lambda)`, while solvent–solvent interactions remain
physical. This creates a solute effective-temperature ladder without heating
the full solvent box.

The build converts the AMBER system with ParmEd, marks only protein atom types,
creates scaled topologies with PLUMED `partial_tempering`, and compares the
scale-one and original potential energies. A PLUMED-patched MPI GROMACS build
with HREX support is required.

GROMACS 2026.3 is not listed among the official PLUMED 2.10 patch targets.
`run.sh` checks the actual `gmx_mpi mdrun -h` output for both `-hrex` and
`-plumed` instead of assuming compatibility from the version number.

`convert_topology.py` performs the AMBER-to-GROMACS conversion, `mark_hot.py`
marks protein atom types, `build.sh` generates and verifies eight states,
`run.sh` uses `-multidir -replex 1000`, and `anal.py` summarizes exchange and
structure. All thermostats remain at `ref-t=300`; hydrogen bonds are constrained
for a 2 fs timestep. `ENERGY_TOLERANCE_KJ_MOL` controls the scale-one check.

The analysis writes exchange acceptance, state visits, occupancy, radius of
gyration, and terminal Cα distance as TSV files. High-temperature compaction
in REST2 has been used intentionally to assist mini-protein folding sampling;
this short example does not establish convergence or force-field quality.
