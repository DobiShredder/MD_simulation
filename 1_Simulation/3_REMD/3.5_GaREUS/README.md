# Gaussian accelerated REUS

## 한국어

REUS의 terminal Cα distance CV와 19개 window에 dual-boost GaMD를 결합합니다.
Window는 6–24 Å, 1 Å 간격이고
`rk2=rk3=10 kcal mol⁻¹ Å⁻²`입니다.

GaREUS는 CV 방향의 umbrella/replica exchange와 CV에 포함되지 않은 자유도의
GaMD acceleration을 동시에 사용합니다. 두 bias가 함께 작동하므로 window
overlap뿐 아니라 exchange mixing, GaMD boost distribution과 reweighting 조건을
각각 확인해야 합니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 1UAO의 첫 NMR model을 simulation PDB로 정리합니다. |
| `make_restraints.py` | Terminal Cα index와 19개 window restraint를 생성합니다. |
| `build.sh` | 공통 topology, state table, restraint와 replica별 seed를 배치합니다. |
| `run.sh` | Window별 pre-production, GaMD parameter preparation과 GaREUS exchange를 실행합니다. |
| `anal.py` | Exchange/occupancy, restraint sampling과 GaMD boost 범위를 계산합니다. |

각 window에서 minimization, 200 ps heating과 1 ns equilibration을 실행한 뒤
4 ns 동안 GaMD parameter를 준비합니다. `igamd=3`,
`sigma0P=sigma0D=6.0`을 사용하며 이 상태를
`irest_gamd=1`로 이어받아 10개의 1 ns GaREUS segment를 실행합니다.
교환은 1 ps마다 시도합니다.

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

단일-window stage는 `pmemd.cuda`, GaREUS는
`pmemd.cuda.MPI -rem 3`를 기본으로 사용합니다. Engine, MPI launcher,
process 수, GPU mapping과 추가 option은 REUS 예제와 같은 environment
variable로 지정합니다. GPU mapping은 scheduler 또는
`CUDA_VISIBLE_DEVICES`에서 설정합니다.

각 window는 고유한 positive seed와 `gamd.prepare.log`를 사용합니다.
Production segment는 `gamd.production.NNN.log`를 따로 기록합니다. 일부
window만 완료된 stage 또는 segment는 자동으로 덮어쓰거나 resume하지
않습니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `igamd=3`, `iE=1` | Total potential과 dihedral potential에 dual boost를 적용하고 lower-bound threshold를 사용합니다. |
| `sigma0P=sigma0D=6.0` | 두 boost의 target standard deviation 상한(kcal/mol)입니다. |
| `irest_gamd=0/1` | Preparation에서 GaMD statistics를 만들고 production에서 해당 state를 이어받습니다. |
| `ntcmdprep`, `ntcmd`, `ntebprep`, `nteb` | Initial conventional statistics와 GaMD equilibration schedule을 정의합니다. `*prep`과 전체 step 값을 독립 구간처럼 더하지 않습니다. |
| `-rem 3`, `nstlim=500`, `numexchg=1000` | Umbrella Hamiltonian을 500 steps, 즉 1 ps마다 교환하고 1 ns segment를 만듭니다. |
| `-gamd` | 현재 GaREUS runner가 window/segment별 boost 기록을 별도 log에 저장할 때 사용합니다. AMBER version별 option 이름을 실제 engine help와 대조합니다. |

`gamd-restart.dat`은 filename이 고정되어 있고 multipmemd는 replica output에
suffix를 붙입니다. Amber 26 GPU에서 replica별 state read/write가 분리되는지
확인하기 전에는 실제 실행에 `ALLOW_UNVERIFIED_GAREUS=1`이 필요합니다.

### Output

- `work/replicas/NNN/production.001.nc` … `production.010.nc`
- `work/replicas/NNN/gamd.production.001.log` …
  `gamd.production.010.log`
- `work/exchange_summary.tsv`, `replica_visits.tsv`,
  `window_occupancy.tsv`
- `work/restraint_sampling.tsv`, `boost_potential.tsv`

`boost_potential.tsv`는 AMBER GaMD log의 마지막 numeric column을 total boost
potential로 읽습니다. AMBER version에서 log column 순서가 다르면
`anal.py`의 parser를 해당 header에 맞게 수정합니다.

## English

This example combines dual-boost GaMD with the same 19 terminal-Cα distance
windows used by REUS. Each window is minimized, heated for 200 ps, equilibrated
for 1 ns, and run for 4 ns of GaMD parameter preparation. The resulting GaMD
state is continued with `irest_gamd=1` into ten 1 ns GaREUS segments.
Exchanges are attempted every 1 ps.

GaREUS combines umbrella/replica exchange along the selected CV with GaMD
acceleration of other energetic degrees of freedom. Window overlap, exchange
mixing, boost distributions, and reweighting quality therefore require separate
checks.

The defaults are `igamd=3` and `sigma0P=sigma0D=6.0`. Each window has a
unique positive seed and separate GaMD logs. The run uses `pmemd.cuda` for
individual stages and `pmemd.cuda.MPI -rem 3` for replica exchange, with
environment overrides for engines and MPI settings.

`igamd=3`, `iE=1` select lower-bound dual boost; `sigma0P` and `sigma0D` cap
the target boost standard deviations. The `ntcmd*` and `nteb*` controls define
overlapping conventional-statistics and GaMD-equilibration schedules, not four
durations to sum. Production switches to
`irest_gamd=1` and uses `-rem 3`, `nstlim=500`, and `numexchg=1000` for 1 ps
exchange attempts and a 1 ns segment. Actual execution requires
`ALLOW_UNVERIFIED_GAREUS=1` until per-replica handling of the fixed
`gamd-restart.dat` name is confirmed with Amber 26 multipmemd.
The current runner uses `-gamd` for per-window logs; confirm the accepted log
option against the target AMBER build.

Analysis writes exchange, visits, occupancy, restraint sampling, and boost
potential ranges as TSV files. The boost parser treats the final numeric GaMD
log column as the total boost and should be adjusted if an AMBER build uses a
different log layout.
