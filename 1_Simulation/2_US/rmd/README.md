# Ratchet MD with PLUMED ABMD / PLUMED ABMD ratchet MD

## 한국어

PDB 1UAO의 첫 NMR model에서 residue 1–10 Cα distance를 증가시킵니다.
기본 index는 terminal Cα atom 2·132와 protein atom 1–138입니다. PLUMED는
`WHOLEMOLECULES` 적용 후 `NOPBC` distance를 계산합니다. Topology가 바뀌면
index도 바꿉니다.

PLUMED `ABMD`는 목표값과 CV 차이로 정의한 ρ를 이용합니다. 기본값은
`TO=3.0 nm`, `KAPPA=100`입니다. `KAPPA`는 일반 harmonic restraint와
definition이 다릅니다. `ratchet.end_to_end_min`도 distance가 아니라 PLUMED의
ρ minimum입니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | 공통 topology를 읽고 minimization, heating, equilibration과 ABMD production을 실행합니다. |
| `inputs/plumed.dat` | Molecule reconstruction, terminal distance와 ABMD bias를 정의합니다. |
| `inputs/ratchet.in` | PLUMED를 활성화한 1 ns NPT AMBER production input입니다. |
| `anal.py` | Cpptraj distance에서 ordered first-crossing frame을 찾고 restart seed를 저장합니다. |

```bash
cd 1_Simulation/2_US
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./prepare.sh
cd rmd
./run.sh --dry-run
./run.sh
python3 anal.py --dry-run
python3 anal.py
```

`run.sh`는 minimization, 200 ps NVT heating, 100 ps NPT equilibration과
1 ns ratchet MD를 실행합니다. 기본 engine은 PLUMED가 연결된
`pmemd.cuda`입니다. NPT 종료 density가 0.90–1.10 g/cm³ 범위를 벗어나면
ratchet MD를 시작하지 않습니다. Output은 `work/ratchet.nc`,
`work/ratchet.rst7`과 `work/ratchet.dat`입니다. `run.sh`는
`inputs/plumed.dat`을 `work/`에 복사한 뒤 AMBER에 넘깁니다.

NPT 중 box-change error, temperature·energy 급등, NaN 또는 SHAKE failure가
발생하면 equilibration을 나누지 않습니다. 상위 `tleap.in`의 periodic
box, `min-all.out`과 `heat.out`을 먼저 확인합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `DISTANCE ATOMS=2,132 NOPBC` | 현재 topology의 terminal Cα atom index입니다. `WHOLEMOLECULES` 뒤에 계산합니다. |
| `ABMD TO=3.0` | End-to-end distance target이며 PLUMED 기본 length unit인 nm를 사용합니다. |
| `KAPPA=100` | Target 반대 방향의 ρ 증가를 억제하는 ratchet strength입니다. Harmonic distance force constant와 직접 비교하지 않습니다. |
| `plumed=1`, `plumedfile='plumed.dat'` | AMBER에서 PLUMED bias를 활성화합니다. |
| `--max-error 0.5` | `anal.py`가 target center와 seed frame 사이에 허용하는 distance 차이(Å)입니다. |
| `--allow-unmarked` | 이 workflow 밖에서 만든 trajectory를 분석할 때만 completion marker 검사를 생략합니다. |
| `SYSTEM_DIR`, `WORK_DIR`, `AMBER_ENGINE` | 공통 topology 위치, output directory와 PLUMED-enabled engine을 지정합니다. |

`anal.py`는 cpptraj으로 `:1@CA`–`:10@CA` distance를 계산하고 각 window
center의 first-crossing frame을 선택합니다. 허용 오차는 0.5 Å입니다. Seed는
`work/seeds/seed_NNN.rst7`, 선택 정보는 `seeds.tsv`에 저장됩니다. 오차 범위
안의 frame이 없으면 종료합니다.

ABMD trajectory는 seed 생성에만 사용합니다. Equilibrium PMF와 kinetics는
이 trajectory에서 계산하지 않습니다.

## English

Ratchet MD increases the terminal Cα distance of the first 1UAO model. The
default indices are Cα atoms 2 and 132 and protein atoms 1–138.
`WHOLEMOLECULES` is applied before the `NOPBC` distance. Update these indices
when the topology changes.

PLUMED ABMD restrains backward progress in ρ, the squared difference between
the CV and its target. The training defaults are `TO=3.0 nm` and `KAPPA=100`.
Because ABMD acts on ρ, its KAPPA does not have the same dimensional convention
as an ordinary AMBER harmonic-distance restraint. The reported `_min`
component is the PLUMED ρ minimum, not a minimum distance.

`run.sh` handles the AMBER stages and activates `inputs/plumed.dat` through
`plumed=1`. The PLUMED file reconstructs the protein, evaluates
`DISTANCE ATOMS=2,132 NOPBC`, and applies `ABMD TO=3.0 KAPPA=100` in PLUMED
units. `anal.py --max-error` controls the allowed Å difference when selecting
first-crossing seeds. Analysis requires the production completion marker by
default; use `--allow-unmarked` only for a trajectory created outside this
workflow. `SYSTEM_DIR`, `WORK_DIR`, and `AMBER_ENGINE` select the
shared system, output location, and PLUMED-enabled executable.

`run.sh` performs minimization, 200 ps NVT heating, 100 ps NPT equilibration,
and 1 ns ratchet MD with a PLUMED-enabled `pmemd.cuda`. It stops before ratchet
MD when the final NPT density is outside 0.90–1.10 g/cm³. NPT box-change errors
are handled by checking the initial periodic box, minimization, and heating
rather than splitting an unsuitable equilibration into short jobs.

The PLUMED input is copied into `work/`. `anal.py` selects ordered
first-crossing frames within 0.5 Å and writes AMBER restart seeds. It exits
when a requested window was not sampled. The biased pathway is used for seed
generation, not for an equilibrium PMF or kinetics.
