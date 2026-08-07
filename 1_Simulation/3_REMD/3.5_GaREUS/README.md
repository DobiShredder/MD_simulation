# Gaussian accelerated REUS

## 한국어

REUS의 terminal Cα distance CV와 19개 window에 dual-boost GaMD를 결합합니다.
Window는 6–24 Å, 1 Å 간격이고
`rk2=rk3=10 kcal mol⁻¹ Å⁻²`입니다.

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

The defaults are `igamd=3` and `sigma0P=sigma0D=6.0`. Each window has a
unique positive seed and separate GaMD logs. The run uses `pmemd.cuda` for
individual stages and `pmemd.cuda.MPI -rem 3` for replica exchange, with
environment overrides for engines and MPI settings.

Analysis writes exchange, visits, occupancy, restraint sampling, and boost
potential ranges as TSV files. The boost parser treats the final numeric GaMD
log column as the total boost and should be adjusted if an AMBER build uses a
different log layout.
