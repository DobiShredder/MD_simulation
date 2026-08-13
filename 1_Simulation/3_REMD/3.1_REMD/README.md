# Temperature REMD

## 한국어

Chignolin(PDB 1UAO)을 ff19SB/TIP3P로 만들고 20-replica T-REMD를 실행합니다.
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
| `build.sh` | ff19SB/TIP3P topology를 만들고 선택한 state file의 temperature·seed로 replica input을 생성합니다. |
| `run.sh` | Replica별 heating/equilibration과 `pmemd.cuda.MPI` exchange segment를 실행합니다. |
| `anal.py` | `remlog`에서 acceptance, state 방문, round trip과 temperature occupancy를 계산합니다. |

### 실행

AMBER 26의 `tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`와 MPI launcher가
필요합니다.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`AMBER_ENGINE`, `AMBER_MPI_ENGINE`, `MPI_LAUNCHER`,
`MPI_PROCESSES`, `MPI_OPTIONS`와 `AMBER_OPTIONS`로 실행 환경을
바꿀 수 있습니다. 기본 MPI process 수는 state file의 data row 수이며 replica
수와 같아야 합니다.

새 system에서는
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)에
실제 protein atom 수, water molecule 수, constraint, NPT temperature 범위와
목표 exchange probability를 입력해 `states.tsv`의 temperature를 정합니다.
이 predictor는 OPLS/AA와 GROMACS 자료로 보정되었으므로 ff19SB/AMBER에서
동일한 acceptance를 보장하지 않습니다. 짧은 pilot run의 adjacent acceptance와
round trip을 보고 replica 수와 temperature 간격을 다시 조정합니다.

기본 `inputs/states.tsv`는 Chignolin의 atom과 water 수로 미리 계산한
20-replica file입니다. 다른 system에서는 generator 결과를 다음 형식의
tab-separated file로 저장해 사용합니다.

```text
replica<TAB>temperature_K<TAB>seed
000<TAB>300.00<TAB>104729
001<TAB>303.65<TAB>112648
```

```bash
./build.sh structure/chignolin.pdb /path/to/states.tsv
./run.sh --dry-run
```

Replica ID는 `000`부터 시작하는 세 자리 고유 값이고 temperature는 행 순서대로
증가해야 합니다. `build.sh`는 선택한 file을 `work/states.tsv`로 복사하며,
`run.sh`는 이 file에서 temperature와 replica 수를 읽습니다.

Heating은 200 ps, NPT equilibration은 100 ps입니다. Production input 하나는
1 ns이고 `run.sh`가 segment 하나를 실행합니다. 모든 replica가
완료된 마지막 segment에서만 이어서 실행합니다. 일부 replica에만 restart
file이 있으면 해당 stage를 자동으로 덮어쓰지 않습니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `-rem 1` | AMBER temperature REMD mode를 선택합니다. |
| `temp0=@TEMP@` | `states.tsv`의 replica별 target temperature로 치환됩니다. |
| `nstlim=500`, `numexchg=1000` | REMD에서 `nstlim`은 교환 사이의 step 수입니다. 500 steps마다 1,000회 교환하여 segment당 1 ns가 됩니다. |
| `ig=@SEED@` | Replica마다 다른 positive random seed를 사용합니다. |
| `build.sh INPUT.pdb [states.tsv]` | 첫 argument의 PDB로 topology를 만들고 temperature·seed file을 선택합니다. State file을 생략하면 Chignolin용 `inputs/states.tsv`를 사용합니다. |
| `MPI_PROCESSES` | AMBER replica 수와 MPI rank 수를 1:1로 맞춥니다. 기본값은 state file의 data row 수입니다. |
| `AMBER_MPI_ENGINE`, `MPI_LAUNCHER`, `MPI_OPTIONS` | MPI executable과 launcher 설정을 바꿉니다. |

### Output

- `work/NNN/production.001.nc`
- `work/exchange.001.log`
- `work/exchange_summary.tsv`
- `work/replica_visits.tsv`
- `work/temperature_occupancy.tsv`

교환 acceptance와 round trip은 sampling 확인 지표입니다. 짧은 교육용 계산의
수치만으로 수렴을 판단하지 않습니다.

## English

This example builds ff19SB/TIP3P Chignolin and runs 20-replica T-REMD from
300 to 373 K. Heating is 200 ps, NPT equilibration is 100 ps, and production is
one 1 ns segment per replica. Exchanges are attempted every 1 ps.

T-REMD keeps one Hamiltonian and varies bath temperature. High-temperature
replicas cross barriers more readily, while accepted swaps move configurations
through the ladder. `build.sh` expands `states.tsv`; `run.sh` uses
`pmemd.cuda.MPI -rem 1`; `anal.py` measures acceptance, visits, round trips,
and occupancy.

`temp0` and `ig` are replica-specific. In AMBER REMD, `nstlim=500` is the step
count between attempts and `numexchg=1000` gives a 1 ns segment.
`MPI_PROCESSES` must equal the state-file row count; the MPI engine, launcher, and
extra options are configurable through the documented environment variables.

Run `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py`
in that order. AMBER and MPI commands can be overridden with the environment
variables listed above. Restarting is allowed only from the last segment
completed by every replica; a partial segment is reported as an error.

For a new system, generate `states.tsv` temperatures with the
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)
using the actual protein-atom and water-molecule counts, constraints, NPT
temperature range, and target exchange probability. Its model was calibrated
with OPLS/AA and GROMACS, so verify adjacent acceptance and round trips in a
short ff19SB/AMBER pilot before fixing the ladder.

The bundled `inputs/states.tsv` is precomputed from the Chignolin atom and
water counts. For a different system, save the generator result as a
tab-separated file with columns `replica`, `temperature_K`, and `seed`, then
run `./build.sh structure/chignolin.pdb /path/to/states.tsv`. Replica IDs are unique
three-digit values starting at `000`, and temperatures increase by row. The
build copies the selected file to `work/states.tsv`; the runner reads its
temperatures and replica count.

The analysis writes adjacent-state acceptance, replica state ranges, round-trip
counts, and temperature occupancy as TSV files. These short training runs do
not establish convergence.
