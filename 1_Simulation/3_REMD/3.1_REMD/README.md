# Temperature REMD

## 한국어

Chignolin(PDB 1UAO)을 ff19SB/TIP3P로 만들고 20-replica T-REMD를 실행합니다.
Temperature는 300–373 K이며 replica당 production은 10 ns입니다.

### 실행

AMBER 26의 `tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`와 MPI launcher가
필요합니다.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

`AMBER_ENGINE`, `AMBER_MPI_ENGINE`, `MPI_LAUNCHER`,
`MPI_PROCESSES`, `MPI_OPTIONS`와 `AMBER_OPTIONS`로 실행 환경을
바꿀 수 있습니다. 기본 MPI process 수는 20이며 replica 수와 같아야 합니다.

Heating은 200 ps, NPT equilibration은 1 ns입니다. Production input 하나는
1 ns이고 `run.sh`가 10개 segment를 순서대로 실행합니다. 모든 replica가
완료된 마지막 segment에서만 이어서 실행합니다. 일부 replica에만 restart
file이 있으면 해당 stage를 자동으로 덮어쓰지 않습니다.

### Output

- `work/replicas/NNN/production.001.nc` … `production.010.nc`
- `work/exchange.001.log` … `exchange.010.log`
- `work/exchange_summary.tsv`
- `work/replica_visits.tsv`
- `work/temperature_occupancy.tsv`

교환 acceptance와 round trip은 sampling 확인 지표입니다. 짧은 교육용 계산의
수치만으로 수렴을 판단하지 않습니다.

## English

This example builds ff19SB/TIP3P Chignolin and runs 20-replica T-REMD from
300 to 373 K. Heating is 200 ps, NPT equilibration is 1 ns, and production is
ten 1 ns segments per replica. Exchanges are attempted every 1 ps.

Run `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py`
in that order. AMBER and MPI commands can be overridden with the environment
variables listed above. Restarting is allowed only from the last segment
completed by every replica; a partial segment is reported as an error.

The analysis writes adjacent-state acceptance, replica state ranges, round-trip
counts, and temperature occupancy as TSV files. These short training runs do
not establish convergence.

