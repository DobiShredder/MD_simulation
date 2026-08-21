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
| `build.sh` | ff19SB/TIP3P topology를 만들고 bundled state file의 temperature·seed로 replica input을 생성합니다. |
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
바꿀 수 있습니다. MPI process 수는 bundled state 수와 같은 20으로 고정됩니다.

새 system에서는
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)에
실제 protein atom 수, water molecule 수, constraint, NPT temperature 범위와
목표 exchange probability를 입력해 `states.tsv`의 temperature를 정합니다.
이 predictor는 OPLS/AA와 GROMACS 자료로 보정되었으므로 ff19SB/AMBER에서
동일한 acceptance를 보장하지 않습니다. 짧은 pilot run의 adjacent acceptance와
round trip을 보고 replica 수와 temperature 간격을 다시 조정합니다.

기본 `inputs/states.tsv`는 Chignolin의 atom과 water 수로 미리 계산한
20-replica file입니다. 다른 system과 temperature ladder는
`3_Templates/3_REMD/3.1_REMD`에서 설정합니다.

```text
replica<TAB>temperature_K<TAB>seed
000<TAB>300.00<TAB>104729
001<TAB>303.65<TAB>112648
```

Replica ID는 `000`부터 시작하는 세 자리 고유 값이고 temperature는 행 순서대로
증가해야 합니다. `build.sh`는 bundled file을 `work/states.tsv`로 복사하며,
`run.sh`는 이 file에서 temperature와 replica 수를 읽습니다.

Heating은 200 ps, NPT equilibration은 100 ps, production은 1 ns입니다.
Preparation stage의 output과 restart가 모든 replica에 있으면 건너뜁니다.
일부 replica의 결과만 있으면 state를 맞추기 위해 해당 stage를 전부 다시
실행합니다. Production output은 덮어쓰지 않습니다.

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

## English

This example builds ff19SB/TIP3P Chignolin and runs 20-replica T-REMD from
300 to 373 K. Heating is 200 ps, NPT equilibration is 100 ps, and production is
1 ns per replica. Exchanges are attempted every 1 ps.

T-REMD keeps one Hamiltonian and varies bath temperature. High-temperature
replicas cross barriers more readily, while accepted swaps move configurations
through the ladder. `build.sh` expands `states.tsv`; `run.sh` uses
`pmemd.cuda.MPI -rem 1`; `anal.py` measures acceptance, visits, round trips,
and occupancy.

`temp0` and `ig` are replica-specific. In AMBER REMD, `nstlim=500` is the step
count between attempts and `numexchg=1000` gives a 1 ns run. The runner launches
one MPI process for each of the 20 bundled states.

Run `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py`
in that order. A preparation stage is skipped when every replica has its output
and restart; an incomplete replica set is rerun. Production output is not
overwritten.

For a new system, generate `states.tsv` temperatures with the
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)
using the actual protein-atom and water-molecule counts, constraints, NPT
temperature range, and target exchange probability. Its model was calibrated
with OPLS/AA and GROMACS, so verify adjacent acceptance and round trips in a
short ff19SB/AMBER pilot before fixing the ladder.

The bundled `inputs/states.tsv` is precomputed from the Chignolin atom and
water counts. Use `3_Templates/3_REMD/3.1_REMD` for another system or
temperature ladder. Replica IDs are unique three-digit values starting at
`000`, and temperatures increase by row. The build copies the bundled file to
`work/states.tsv`.

The analysis writes adjacent-state acceptance, replica state ranges, round-trip
counts, and temperature occupancy as TSV files. Replica trajectories are
written to `work/NNN/production.nc`. These short training runs do not
establish convergence.
