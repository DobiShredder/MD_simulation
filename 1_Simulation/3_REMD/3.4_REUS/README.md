# Replica Exchange Umbrella Sampling

## 한국어

Chignolin의 residue 1과 10 Cα distance를 CV로 사용하는 REUS 예제입니다.
6–24 Å를 1 Å 간격으로 나눈 19개 window를 같은 온도에서 교환합니다.
`rk2=rk3=10 kcal mol⁻¹ Å⁻²`이며, heating 200 ps, equilibration 1 ns,
production은 window당 10 ns입니다. 교환은 1 ps마다 시도합니다.

### 실행

AMBER 26, ParmEd와 19개 MPI process가 필요합니다.

```bash
python3 -m pip install -r requirements.txt
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

`make_restraints.py`는 ff19SB/TIP3P topology에서 `:1@CA`와
`:10@CA`의 atom index를 찾습니다. 각 window의 `distance.RST`에 실제
index와 restraint center를 기록하므로 다른 system에 적용할 때 selection과
window 범위를 먼저 바꿉니다.

기본 engine은 단일-window stage에 `pmemd.cuda`, replica exchange에
`pmemd.cuda.MPI -rem 3`입니다. `AMBER_ENGINE`,
`AMBER_MPI_ENGINE`, `MPI_LAUNCHER`, `MPI_PROCESSES`,
`MPI_OPTIONS`와 `AMBER_OPTIONS`로 실행 환경을 지정합니다.

Production은 10개의 1 ns segment입니다. 모든 window가 완료된 마지막
segment에서만 이어서 실행합니다.

### Output

- `work/replicas/NNN/production.001.nc` … `production.010.nc`
- `work/exchange_summary.tsv`, `replica_visits.tsv`,
  `window_occupancy.tsv`
- `work/restraint_sampling.tsv`

Window overlap과 PMF는
[umbrella-sampling analysis](../../../2_Analysis/7_Enhanced_Sampling/README.md)에서
계산합니다.

## English

This REUS example exchanges 19 windows along the Chignolin residue 1–10 Cα
distance. Centers span 6–24 Å at 1 Å spacing, with
`rk2=rk3=10 kcal mol⁻¹ Å⁻²`. Heating is 200 ps, equilibration is 1 ns,
production is ten 1 ns segments per window, and exchanges are attempted every
1 ps.

The build resolves the two Cα atom indices from the ff19SB/TIP3P topology and
writes one restraint per window. The run uses `pmemd.cuda` for individual
stages and `pmemd.cuda.MPI -rem 3` for exchange. Partial segments are not
silently resumed.

Analysis writes acceptance, state visits, window occupancy, and sampled
restraint-distance ranges as TSV files. Use the linked analysis tutorial for
overlap and PMF calculation.
