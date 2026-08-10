# Replica-exchange simulations / Replica exchange 시뮬레이션

![Replica exchange에서 state와 walker의 이동 / State and walker motion in replica exchange](../../assets/simulation/replica_exchange.svg)

*State는 ladder에 남고 accepted exchange를 통해 walker가 여러 state를 방문합니다. / States remain on the ladder while accepted exchanges let walkers visit different states.*


## 한국어

다섯 예제 모두 Chignolin(PDB 1UAO)을 ff19SB/TIP3P로 만들며 다른 tutorial의
output을 사용하지 않습니다.

Replica exchange는 서로 다른 thermodynamic state 또는 Hamiltonian을 병렬로
계산하고 주기적으로 state 교환을 시도합니다. Metropolis criterion을 만족하는
교환은 각 replica가 barrier를 우회하도록 돕지만, replica 수·state 간격·교환
빈도와 round trip을 함께 점검해야 합니다.

| 순서 | Method | Replica/state | Engine |
| ---: | --- | ---: | --- |
| 3.1 | [T-REMD](3.1_REMD/README.md) | 20 temperatures | `pmemd.cuda.MPI -rem 1` |
| 3.2 | [REST2](3.2_REST2/README.md) | 8 effective temperatures | GROMACS/PLUMED HREX |
| 3.3 | [REST3](3.3_REST3/README.md) | 8 λ/κ states | GROMACS/PLUMED HREX |
| 3.4 | [REUS](3.4_REUS/README.md) | 19 distance windows | `pmemd.cuda.MPI -rem 3` |
| 3.5 | [GaREUS](3.5_GaREUS/README.md) | 20 distance windows | `pmemd.cuda.MPI -rem 3` |

각 폴더에서 다음 순서로 실행합니다.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

공통으로 `download.sh`는 source structure를 받고, `prepare.py`는 첫 NMR model을
정리합니다. `build.sh`는 topology와 replica별 input을 만들며, `run.sh`는
pre-production과 replica exchange를 실행합니다. `anal.py`는 exchange log에서
acceptance, state 방문, occupancy와 round trip을 계산합니다. REST2/REST3에는
scaled topology를 만드는 추가 helper가 있습니다.

Production은 replica당 1 ns이며 1 ns segment 하나로 나뉩니다. 모든
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
and 20-window GaREUS with the engines listed in the table above.

Replica exchange propagates parallel thermodynamic states or Hamiltonians and
periodically proposes state swaps using a Metropolis criterion. Useful mixing
depends on state spacing, exchange acceptance, state visits, and round trips,
not on exchange attempts alone.

Use `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py`
in order. Production is one 1 ns segment per replica. A run resumes only from
the last segment completed by every replica; partial segments are reported as
errors. Engine and MPI settings are supplied through the environment variables
documented by each method.

In every folder, download and preparation handle the source structure, build
creates topology/state inputs, run performs pre-production and exchange, and
analysis parses exchange and occupancy statistics. REST2/REST3 add topology-
scaling helpers documented in their local READMEs.
