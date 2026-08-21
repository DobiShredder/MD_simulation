# T-REMD template

## 한국어

사용자가 준비한 protein PDB로 AMBER temperature replica exchange를 구성합니다.
`build.sh`는 ff19SB/OPC system을 만든 뒤 topology의 solute/ion atom 수와 water
molecule 수를 읽어 300–450 K ladder를 자동 생성합니다. 기본 목표 neighboring
exchange probability는 0.20이며 예측값은 initial schedule을 정하는 근사치입니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`pmemd.cuda`가 각 replica의 minimization, heating과 equilibration을 실행합니다.
Production은 replica 수와 같은 수의 MPI process에서 `pmemd.cuda.MPI -rem 1`로
실행합니다. 실제 replica 수는 `work/states.tsv`에서 확인합니다. MPI process의
node와 GPU 배치는 `MPI_OPTIONS`와 cluster scheduler에서 설정합니다.

`temperature_mode = "file"`을 쓰면 `temperature_file`의 값을 그대로 사용합니다.
Comma, semicolon, vertical bar와 whitespace를 구분자로 받습니다. Generated
input과 적용값은 `work/resolved_config.toml`에 기록됩니다.

## English

This template builds AMBER temperature replica exchange from a user-prepared
protein PDB. In automatic mode, the ff19SB/OPC topology supplies solute/ion atom
and water-molecule counts to the offline temperature predictor. The default
range is 300–450 K with a target neighboring exchange probability of 0.20.

`pmemd.cuda` runs preproduction for each replica. Production uses
`pmemd.cuda.MPI -rem 1` with one MPI process per replica; process and GPU
placement remain scheduler settings. The generated replica count and
temperatures are recorded in `work/states.tsv`. File mode accepts comma,
semicolon, vertical-bar, or whitespace-separated temperatures.
