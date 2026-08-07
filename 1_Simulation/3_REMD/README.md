# Replica-exchange simulations / Replica exchange 시뮬레이션

## 한국어

다섯 예제 모두 Chignolin(PDB 1UAO)을 ff19SB/TIP3P로 만들며 다른 tutorial의
output을 사용하지 않습니다.

| 순서 | Method | Replica/state | Engine |
| ---: | --- | ---: | --- |
| 3.1 | [T-REMD](3.1_REMD/README.md) | 20 temperatures | `pmemd.cuda.MPI -rem 1` |
| 3.2 | [REST2](3.2_REST2/README.md) | 8 effective temperatures | GROMACS/PLUMED HREX |
| 3.3 | [REST3](3.3_REST3/README.md) | 8 λ/κ states | GROMACS/PLUMED HREX |
| 3.4 | [REUS](3.4_REUS/README.md) | 19 distance windows | `pmemd.cuda.MPI -rem 3` |
| 3.5 | [GaREUS](3.5_GaREUS/README.md) | 19 distance windows | `pmemd.cuda.MPI -rem 3` |

각 폴더에서 다음 순서로 실행합니다.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

Production은 replica당 10 ns이며 1 ns segment 10개로 나뉩니다. 모든
replica가 같은 segment를 완료했을 때만 resume합니다. MPI launcher, engine,
process 수와 추가 option은 각 README에 적힌 environment variable로
지정합니다.

Exchange acceptance, state 방문과 occupancy는 `anal.py`에서 계산합니다.
REUS/GaREUS PMF처럼 더 긴 후처리는
[analysis tutorial](../../2_Analysis/7_Enhanced_Sampling/README.md)에서
다룹니다.

## English

All five examples independently build ff19SB/TIP3P Chignolin. They cover
20-temperature T-REMD, eight-state REST2, eight-state REST3, 19-window REUS,
and 19-window GaREUS with the engines listed in the table above.

Use `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py`
in order. Production is ten 1 ns segments per replica. A run resumes only from
the last segment completed by every replica; partial segments are reported as
errors. Engine and MPI settings are supplied through the environment variables
documented by each method.

