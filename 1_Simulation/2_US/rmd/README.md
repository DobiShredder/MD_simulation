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

`run.sh`는 minimization, 200 ps NVT heating, 1 ns NPT equilibration과
10 ns ratchet MD를 실행합니다. 기본 engine은 PLUMED가 연결된
`pmemd.cuda`입니다. Output은 `work/ratchet.nc`, `work/ratchet.rst7`과
`work/ratchet.dat`입니다. `run.sh`는 `inputs/plumed.dat`을 `work/`에
복사한 뒤 AMBER에 넘깁니다.

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

`run.sh` performs minimization, 200 ps NVT heating, 1 ns NPT equilibration, and
10 ns ratchet MD. The default engine is a PLUMED-enabled `pmemd.cuda`.
The PLUMED input is copied into `work/`. `anal.py` selects ordered
first-crossing frames within 0.5 Å and writes AMBER
restart seeds. It exits when a requested window was not sampled.

The biased pathway is used for seed generation, not for an equilibrium PMF or
kinetics.
