# Temperature REMD

## 한국어

Chignolin(PDB 1UAO)을 ff19SB/OPC로 만들고 18-replica T-REMD를 실행합니다.
Temperature는 300–373 K이며 replica당 production은 1 ns입니다.

T-REMD는 모든 replica에 같은 Hamiltonian을 사용하고 bath temperature만
바꿉니다. 높은 temperature replica는 barrier를 더 쉽게 넘고, 교환을 통해
그 configuration이 낮은 temperature ensemble로 이동합니다. 분석은 walker가
temperature ladder를 왕복하는지와 300 K ensemble을 분리해 확인해야 합니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 1UAO의 첫 NMR model을 simulation PDB로 정리합니다. |
| `build.sh` | ff19SB/OPC topology를 만들고 bundled state file의 temperature·seed로 replica input을 생성합니다. |
| `run.sh` | Replica별 heating/equilibration과 `pmemd.cuda.MPI` exchange calculation을 실행합니다. |
| `anal.py` | `remlog`에서 acceptance, state 방문, round trip과 temperature occupancy를 계산합니다. |

### 실행

AMBER 26의 `tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`와 MPI launcher가
필요합니다.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh
python3 anal.py
```

`AMBER_ENGINE`, `AMBER_MPI_ENGINE`과 `MPI_LAUNCHER`로 executable을
바꿀 수 있습니다. MPI process 수는 bundled state 수와 같은 18로 고정됩니다.

새 system에서는
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)에
실제 protein atom 수, water molecule 수, constraint, NPT temperature 범위와
목표 exchange probability를 입력해 `states.tsv`의 temperature를 정합니다.
이 predictor는 OPLS/AA와 GROMACS 자료로 보정되었으므로 ff19SB/AMBER에서
동일한 acceptance를 보장하지 않습니다. 짧은 pilot run의 adjacent acceptance와
round trip을 보고 replica 수와 temperature 간격을 다시 조정합니다.

기본 `inputs/states.tsv`는 OPC Chignolin의 140개 solute/ion atom과 1,755개
water molecule을 사용해 목표 인접 교환확률 0.20으로 계산한 18-replica
file입니다. 마지막 373 K state는 상한을 정확히 포함하므로 바로 아래 state와의
예측 acceptance가 목표값보다 높습니다. 다른 system과 temperature ladder는
`3_Templates/3_REMD/3.1_T-REMD`에서 설정합니다.

```text
replica<TAB>temperature_K<TAB>seed
000<TAB>300.00<TAB>104729
001<TAB>303.65<TAB>112648
```

Replica ID는 `000`부터 시작하는 세 자리 고유 값이고 temperature는 행 순서대로
증가해야 합니다. `build.sh`는 bundled file을 `work/states.tsv`로 복사하며,
`run.sh`는 이 file에서 temperature와 replica 수를 읽습니다.

Heating은 200 ps, NPT equilibration은 100 ps, production은 1 ns입니다.
완료 marker와 필수 output이 있는 stage만 건너뜁니다. 불완전하거나 marker가
없는 기존 결과는 보존하고 중단합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `-rem 1` | AMBER temperature REMD mode를 선택합니다. |
| `temp0=@TEMP@` | `states.tsv`의 replica별 target temperature로 치환됩니다. |
| `nstlim=500`, `numexchg=1000` | REMD에서 `nstlim`은 교환 사이의 step 수입니다. 500 steps마다 1,000회 교환하여 총 1 ns가 됩니다. |
| `ig=@SEED@` | Replica마다 다른 positive random seed를 사용합니다. |
| `build.sh INPUT.pdb` | 첫 argument의 PDB와 Chignolin용 `inputs/states.tsv`로 replica를 만듭니다. |
| `AMBER_MPI_ENGINE`, `MPI_LAUNCHER` | MPI executable과 launcher command를 바꿉니다. |

### Output

- `work/NNN/production.nc`
- `work/exchange.log`
- `work/exchange_summary.tsv`
- `work/replica_visits.tsv`
- `work/temperature_occupancy.tsv`

교환 acceptance와 round trip은 sampling 확인 지표입니다. 짧은 교육용 계산의
수치만으로 수렴을 판단하지 않습니다.

### 완료 상태와 재실행

Engine이 성공하고 모든 replica의 필수 output을 확인한 뒤
`work/.STAGE.complete`를 기록합니다. Minimization은 `.out`, `.rst7`,
`.info`를 요구하며 heating, equilibration과 production은 `.nc`도 요구합니다.
Production에는 `work/exchange.log`도 필요합니다.

계산을 시작하기 전에 모든 stage의 상태를 검사합니다. 일부 replica의 결과,
zero-length 파일, marker만 있는 상태 또는 marker 없는 기존 output이 있으면
파일을 덮어쓰지 않고 중단합니다. 기존 결과를 검토·보관한 뒤 별도 tutorial
복사본에서 새 계산을 시작합니다. Marker를 수동으로 만들어 완료 처리하지 않습니다.
정상 완료 후 재실행은 engine을 호출하거나 결과를 다시 쓰지 않습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build 전에는 기존 `work/`를 다른 위치에 보관하거나 별도 tutorial 사본을 사용합니다.

## English

This example builds ff19SB/OPC Chignolin and runs 18-replica T-REMD from
300 to 373 K. Heating is 200 ps, NPT equilibration is 100 ps, and production is
1 ns per replica. Exchanges are attempted every 1 ps.

T-REMD keeps one Hamiltonian and varies bath temperature. High-temperature
replicas cross barriers more readily, while accepted swaps move configurations
through the ladder. `build.sh` expands `states.tsv`; `run.sh` uses
`pmemd.cuda.MPI -rem 1`; `anal.py` measures acceptance, visits, round trips,
and occupancy.

`temp0` and `ig` are replica-specific. In AMBER REMD, `nstlim=500` is the step
count between attempts and `numexchg=1000` gives a 1 ns run. The runner launches
one MPI process for each of the 18 bundled states.

Run `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py`
in that order. A stage is skipped only when its completion marker and required outputs are present.
Incomplete or unmarked results are preserved, and execution stops.

For a new system, generate `states.tsv` temperatures with the
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)
using the actual protein-atom and water-molecule counts, constraints, NPT
temperature range, and target exchange probability. Its model was calibrated
with OPLS/AA and GROMACS, so verify adjacent acceptance and round trips in a
short ff19SB/AMBER pilot before fixing the ladder.

The bundled `inputs/states.tsv` is precomputed for OPC Chignolin from 140
solute/ion atoms and 1,755 water molecules at a target neighboring exchange
probability of 0.20. The final state is clipped to the exact 373 K upper bound,
so its predicted acceptance with the preceding state is higher than the target.
Use `3_Templates/3_REMD/3.1_T-REMD` for another system or
temperature ladder. Replica IDs are unique three-digit values starting at
`000`, and temperatures increase by row. The build copies the bundled file to
`work/states.tsv`.

The analysis writes adjacent-state acceptance, replica state ranges, round-trip
counts, and temperature occupancy as TSV files. Replica trajectories are
written to `work/NNN/production.nc`. These short training runs do not
establish convergence.

### Completion and reruns

The runner writes `work/.STAGE.complete` only after engine success and verification
of every replica’s required outputs. Minimization requires `.out`, `.rst7` and
`.info`; heating, equilibration and production also require `.nc`.
Production additionally requires `work/exchange.log`.

All stage states are checked before computation begins. Partial replica results,
zero-length files, markers without required outputs and unmarked outputs cause
an error without overwriting files. Review and archive retained results, then
start a new calculation in a separate tutorial copy. Do not create markers
manually to adopt old results. A rerun after normal completion invokes no engine
and rewrites no results.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Preserve the existing `work/` elsewhere or use a separate tutorial copy before a new build.

### 동시 실행과 input 변경

Build와 run은 `work.writers/` registry를 공유합니다. 같은 output/state를 쓰는 작업은 동시에 실행하지 않습니다. `prepare.py`가 있는 경우 structure를 생성하는 작업도 input을 읽는 build와 충돌하면 거부합니다.

Run은 재사용할 결과의 input을 SHA256으로 비교합니다. Topology, 최초 coordinate file, stage input, predecessor restart와 restraint가 바뀌거나 기존 결과에 identity 기록이 없으면 파일을 보존하고 거부합니다. 이 tutorial은 고정 경로를 사용하므로 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Build and run share the `work.writers/` registry and reject concurrent writers to the same output/state. Where present, `prepare.py` also rejects structure writes that overlap an active build reader.

Run compares inputs for result reuse with SHA256. Changed topology, initial coordinates, stage input, predecessor restart or restraint, and results without identity records, are preserved and rejected. This tutorial uses fixed paths; start changed calculations in a new tutorial copy.

Normal exit, command failure and INT/TERM release only the owned lock after child termination is verified. Locks left by SIGKILL or node failure are retained. Inspect the reported lock and its `owner.json` host, PID, command and scopes; confirm through the scheduler and owning host that all writers and children stopped before manually removing only that lock directory. A PID missing locally is not sufficient. Apply the same checks to `.gate/`.

Supported `--dry-run` and `--help` do not create writer or identity files. Do not move active work trees or edit identities to reuse results. Protection was tested on a local filesystem with local child processes; network filesystems, remote MPI and termination of writers on other nodes remain unverified.
