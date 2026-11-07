# Replica-exchange templates / Replica-exchange templates

## 한국어

다섯 template는 같은 config 중심 interface를 사용하지만 교환하는 state와 engine이
다릅니다. 각 leaf에는 runtime helper가 별도로 들어 있습니다.

| Directory | 교환하는 state | Production interface |
| --- | --- | --- |
| [`3.1_T-REMD`](3.1_T-REMD/README.md) | 실제 temperature | AMBER `-rem 1` |
| [`3.2_REST2`](3.2_REST2/README.md) | REST2-scaled Hamiltonian | PLUMED `-hrex` |
| [`3.3_REST3`](3.3_REST3/README.md) | REST3-scaled Hamiltonian과 κ | PLUMED `-hrex` |
| [`3.4_REUS`](3.4_REUS/README.md) | Reaction-coordinate umbrella state | AMBER `-rem 3` |
| [`3.5_GaREUS`](3.5_GaREUS/README.md) | Umbrella state와 공통 GaMD boost | AMBER `-rem 3` |

다섯 template 모두 최소 2개·짝수 replica만 지원합니다. 일반 US의 독립 window에는
이 제한을 적용하지 않습니다.

### 준비 사항

| Template | 필요한 executable |
| --- | --- |
| T-REMD, REUS, GaREUS | AMBER `tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`, MPI launcher |
| REST2, REST3 | AMBER `tleap`, PLUMED CLI `plumed`, GROMACS `gmx`, PLUMED-patched `gmx_mpi`, MPI launcher |

Python package는 각 leaf의 `requirements.txt`(NumPy, ParmEd, Python 3.11 미만이면
tomli)로 설치합니다. Executable 이름, `MPI_OPTIONS`와 engine option override는
leaf README에 있습니다. REST2/REST3에서 `gmx`는 build와 pre-production에,
`gmx_mpi`는 HREX production에 사용합니다.

#### REST2/REST3 GROMACS–PLUMED build

REST2와 REST3 production에는 PLUMED 2.10.2 이상으로 patch한
`GROMACS 2024.3` external-MPI build가 필요합니다. 서로 다른 scaled topology를
`-hrex`로 교차 평가하는 경로는 PLUMED의 GROMACS 2024 patch에만 있습니다.
GROMACS 2025/2026 patch와 built-in PLUMED interface에는 이 경로가 없습니다.
PLUMED 2.10.0과 2.10.1의 GROMACS 2024 patch는 swapped coordinate의 energy를
잘못 계산해 exchange가 거의 accept되지 않으며, 2.10.2에서 수정되었습니다
([PLUMED issue #1326](https://github.com/plumed/plumed2/issues/1326)).

GROMACS source root에서 PLUMED patch를 적용하고 external MPI로 build한 뒤
option과 PLUMED patch version을 확인합니다. `-DGMX_GPU=CUDA`는 GPU build에만
붙입니다. GROMACS 기본값인 thread-MPI는 multi-simulation을 지원하지 않으므로
`-multidir` HREX에는 external MPI build(`gmx_mpi`)가 필요합니다.

```bash
plumed patch -p -e gromacs-2024.3
mkdir build
cd build
cmake .. -DGMX_MPI=ON -DGMX_THREAD_MPI=OFF -DGMX_GPU=CUDA
make
make install
gmx_mpi mdrun -h 2>&1 | grep -E -- '-hrex|-plumed'
gmx_mpi --version | grep 'GROMACS version'
```

Version은 `2024.3-plumed_2.10.2`처럼 표시됩니다. REST2/REST3 runner도
production 시작 전에 `-hrex`와 이 PLUMED version(2.10.2 이상)을 검사합니다.
GROMACS 2024.6처럼 다른 2024 bugfix release에 2024.3 patch를 적용하는 조합과
실제 GPU/external-MPI HREX 실행은 미검증이므로 설치 환경에서 짧은 pilot run으로
확인합니다.

### 실행

각 leaf directory에서 다음 순서로 실행합니다.

```bash
./build.sh INPUT.pdb
./run.sh --dry-run
./run.sh
```

REST2/REST3는 `run.sh --cpus N --gpus N`으로 resource를 override합니다.
GaREUS의 실제 실행에는 `run.sh --allow-unverified`가 필요합니다(이유는 leaf README 참고).

모든 runner는 `--preparation-only`, `--production-only`와 1-based inclusive
`--segments START-END`를 지원합니다. Exchange production은 선택한 segment의
모든 replica/window를 함께 실행합니다. REUS/GaREUS window subset은 독립적인
exchange ensemble이 아니므로 제공하지 않습니다.

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

T-REMD, REUS, GaREUS의 단일-replica AMBER stage는 engine stdout/stderr를
`<stage>.out` 옆의 `engine.<stage>.log`에 시도마다 header를 붙여 이어서
기록합니다. REST2/REST3 pre-production은 `<stage>.grompp.log`와
`<stage>.mdrun.log`에 기록합니다. Stage가 실패하면 `run.sh`가 이 log의 경로와
마지막 20줄을 출력합니다.

### State schedule 선택

`temperature_mode`의 `auto`/`file` 선택은 T-REMD, REST2와 REST3에만 있습니다.
REST3는 κ의 `linear`/`file` 선택을 추가합니다. REUS와 GaREUS는
`windows_file`에 적힌 umbrella state를 항상 사용하며 이를 mode로 선택하지
않습니다. 허용값과 file validation은 각 leaf README에 정리되어 있습니다.

T-REMD, REST2와 REST3는 같은 offline temperature predictor 계산식을 사용합니다.
각 leaf에는 이 계산에 필요한 code가 별도로 들어 있습니다. T-REMD는
explicit water를 포함한 전체 atom 수를 사용합니다. REST2/REST3는 tempered atom
수(기본은 water와 ion을 제외한 solute 전체, `tempered_mask`로 변경)와 water 0을
사용합니다. `temperature_mode="file"`은
사용자가 제공한 temperature를 그대로 사용합니다. 두 mode 모두 resolved state와
random seed를 `work/states.tsv`에 기록합니다.

생성된 temperature ladder는 근사값이므로 pilot run에서 neighboring acceptance와
round trip을 확인합니다. REST3의 linear κ schedule도 published example을
일반화한 시작값이며 force field와 system별 검증이 필요합니다.

### Exchange 품질 해석

Template에는 `anal.py`가 없습니다. Segment별 engine log를 직접 읽습니다.

| Engine | 읽을 log | Acceptance 위치 |
| --- | --- | --- |
| AMBER (T-REMD, REUS, GaREUS) | `work/exchange.NNN.log` remlog | `# exchange N` block의 replica별 `Success_rate` |
| GROMACS (REST2, REST3) | 각 replica의 `production*.log` | `Repl ex` line과 log 끝의 `Repl average probabilities` |

Column 의미와 leaf별 주의점은 leaf README의 Exchange 품질 해석 section에
있습니다. 판단 기준은 tutorial과 같습니다. 0에 가까운 인접 pair가 없어야 하고,
각 walker가 ladder 양 끝을 방문해 한 번 이상 왕복해야 합니다. 목표 acceptance와
REUS/GaREUS window overlap은
[REMD tutorial family README](../../1_Simulation/3_REMD/README.md#exchange-품질-해석)를
참고합니다.

## English

The five templates use the same config-driven interface but exchange different
states with different engines. Each leaf contains its own runtime helpers.

| Directory | Exchanged state | Production interface |
| --- | --- | --- |
| [`3.1_T-REMD`](3.1_T-REMD/README.md) | Physical temperature | AMBER `-rem 1` |
| [`3.2_REST2`](3.2_REST2/README.md) | REST2-scaled Hamiltonian | PLUMED `-hrex` |
| [`3.3_REST3`](3.3_REST3/README.md) | REST3-scaled Hamiltonian and κ | PLUMED `-hrex` |
| [`3.4_REUS`](3.4_REUS/README.md) | Reaction-coordinate umbrella state | AMBER `-rem 3` |
| [`3.5_GaREUS`](3.5_GaREUS/README.md) | Umbrella state and shared GaMD boost | AMBER `-rem 3` |

All five templates support only even replica counts of at least two.
Independent windows in ordinary US are outside this restriction.

### Prerequisites

| Template | Required executables |
| --- | --- |
| T-REMD, REUS, GaREUS | AMBER `tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`, MPI launcher |
| REST2, REST3 | AMBER `tleap`, PLUMED CLI `plumed`, GROMACS `gmx`, PLUMED-patched `gmx_mpi`, MPI launcher |

Install Python packages from each leaf's `requirements.txt` (NumPy, ParmEd, and
tomli below Python 3.11). Leaf READMEs list the executable-name, `MPI_OPTIONS`
and engine-option overrides. In REST2/REST3, `gmx` runs the build and
pre-production, and `gmx_mpi` runs HREX production.

#### REST2/REST3 GROMACS–PLUMED build

REST2 and REST3 production require an external-MPI build of GROMACS 2024.3
patched with PLUMED 2.10.2 or later. Only the PLUMED patch for GROMACS 2024
provides the `-hrex` path that cross-evaluates differently scaled topologies;
the GROMACS 2025/2026 patches and the built-in PLUMED interface do not. The
GROMACS 2024 patch in PLUMED 2.10.0 and 2.10.1 computes a wrong
swapped-coordinate energy, so exchanges are almost never accepted; PLUMED
2.10.2 fixes this ([PLUMED issue #1326](https://github.com/plumed/plumed2/issues/1326)).

From the GROMACS source root, apply the PLUMED patch, build with external MPI,
and check the options and the PLUMED patch version. Add `-DGMX_GPU=CUDA` only
for a GPU build. The default thread-MPI build does not support multi-simulation
runs, so `-multidir` HREX needs the external-MPI `gmx_mpi`.

```bash
plumed patch -p -e gromacs-2024.3
mkdir build
cd build
cmake .. -DGMX_MPI=ON -DGMX_THREAD_MPI=OFF -DGMX_GPU=CUDA
make
make install
gmx_mpi mdrun -h 2>&1 | grep -E -- '-hrex|-plumed'
gmx_mpi --version | grep 'GROMACS version'
```

The version reads like `2024.3-plumed_2.10.2`. The REST2 and REST3 runners
repeat the `-hrex` check and require PLUMED 2.10.2 or later before production.
Applying the 2024.3 patch to another 2024 bugfix release such as 2024.6, and an
actual GPU/external-MPI HREX run, are unverified; check them with a short pilot
run in the target installation.

### Run

Run these steps in each leaf directory.

```bash
./build.sh INPUT.pdb
./run.sh --dry-run
./run.sh
```

Use `--cpus` and `--gpus` to override REST2/REST3 replica resources.
GaREUS requires `run.sh --allow-unverified` for actual execution; the leaf
README gives the reason.

Every runner supports `--preparation-only`, `--production-only`, and inclusive
1-based `--segments START-END`. Exchange production always includes every
replica or window of the selected segments, so REUS and GaREUS do not expose a
production-window subset.

See [GUIDE.md appendix](../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

Single-replica AMBER stages in T-REMD, REUS and GaREUS append engine
stdout/stderr to `engine.<stage>.log` beside `<stage>.out`, with a header line
per attempt. REST2/REST3 pre-production writes `<stage>.grompp.log` and
`<stage>.mdrun.log`. When a stage fails, `run.sh` prints the log path and its
last 20 lines.

### Choosing the state schedule

The `auto`/`file` `temperature_mode` choice applies only to T-REMD, REST2 and
REST3. REST3 additionally provides `linear`/`file` κ selection. REUS and GaREUS
always read the umbrella states listed in `windows_file`; this is not a mode
switch. Each leaf README gives the accepted values and file validation.

T-REMD, REST2 and REST3 use the same offline temperature-prediction algorithm,
implemented inside each leaf. T-REMD counts the full solvated system, whereas
REST2/REST3 count the tempered atoms (the whole non-water, non-ion solute by
default, or `tempered_mask`) and supply zero waters.
`temperature_mode="file"` uses the user-supplied temperatures as given. Both
modes record the resolved schedule and random seeds in `work/states.tsv`.

Generated ladders are approximate, so check neighboring acceptance and round
trips in a pilot run. The default REST3 linear κ schedule is likewise a starting
value generalized from a published example and needs force-field- and
system-specific validation.

### Reading exchange quality

The templates have no `anal.py`; read each segment's engine log directly.

| Engine | Log | Where acceptance appears |
| --- | --- | --- |
| AMBER (T-REMD, REUS, GaREUS) | `work/exchange.NNN.log` remlog | Per-replica `Success_rate` in each `# exchange N` block |
| GROMACS (REST2, REST3) | Each replica's `production*.log` | `Repl ex` lines and `Repl average probabilities` at the end of the log |

Leaf READMEs give the columns and leaf-specific notes in their exchange-quality
sections. The criteria match the tutorials: no adjacent pair near zero, and
every walker should reach both ladder ends and complete at least one round
trip. For target acceptance and REUS/GaREUS window overlap, see the
[REMD tutorial family README](../../1_Simulation/3_REMD/README.md#reading-exchange-quality).
