# WESTPA–AMBER weighted ensemble

Reference syntax: Amber 2026 and WESTPA 2.

## 한국어

Na⁺와 Cl⁻를 8 Å 떨어진 상태에서 시작하고 ion distance를 progress coordinate로
사용합니다. WESTPA가 bin당 walker 수를 맞추며 `pmemd.cuda`는 1 ps segment를
직렬로 실행합니다. Dynamics는 implicit solvent를 사용합니다.

### Script 역할

| 파일 | 역할 | 주요 output |
| --- | --- | --- |
| `prepare.py` | 지정한 distance의 two-ion MOL2 생성 | `work/structure/system.mol2` |
| `build.sh` | Topology, minimization과 basis-state equilibration | `work/common_files/`, `work/bstates/` |
| `env.sh` | WESTPA root, work directory와 executable 기본값 설정 | 다른 shell script가 자동으로 호출 |
| `init.sh` | WESTPA HDF5 초기화 | `work/west.h5` |
| `run.sh` | WESTPA work manager 실행 | Segment directory와 `work/west.log` |
| `westpa_scripts/runseg.sh` | Parent restart에서 AMBER segment 전파 | `seg.rst7`, pcoord |
| `anal.py` | Weight 합, occupancy와 target 도달 진단 | `iteration_summary.tsv` 등 |

```bash
python3 prepare.py --distance 8.0
./build.sh
./init.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

### 주요 option

기존 `work/west.h5`를 지우고 새 run을 시작할 때만 `./init.sh --reset`을
사용합니다. 기본 engine은 `pmemd.cuda`이며 walker는 한 GPU에서 serial로
실행합니다. 다른 실행 방식은 WESTPA work manager와 GPU 할당을 함께 설계한 뒤
변경합니다.

CPU에서 workflow를 확인할 때는 `sander`와 process work manager를 지정할 수 있습니다.

```bash
AMBER_ENGINE=sander \
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=8 \
./run.sh
```

`WESTPA_WORKERS`는 동시에 실행할 segment 수입니다. 사용 가능한 CPU core와 memory에
맞춰 값을 정합니다. 기본값은 `serial`과 worker 1개이며, 여러 GPU의 작업 분배는 이
tutorial에서 다루지 않습니다.

`west.cfg`는 bin당 walker 4개, 20 iterations와 2.6 Å bound-state 경계를
사용합니다. `tstate.file`의 2.5 Å는 `[0, 2.6)` bin 안에 놓인 대표값이며
경계 자체가 아닙니다. Segment input의 `irest=1`, `ntx=5`는 parent velocity를 이어받습니다.
Implicit-solvent input의 `igb=1`과 맞추기 위해 tleap에서
`set default PBradii amber6`를 지정합니다.
`WEST_RAND32`에서 각 segment의 positive Langevin seed를 만듭니다. WESTPA가
walker를 복제해도 같은 random-number stream을 반복하지 않기 위한 설정입니다.

`iteration_summary.tsv`의 total weight는 1에 가까워야 합니다. Effective walker
수, sampled distance와 bin occupancy도 함께 확인합니다. `target_events.tsv`는
sampling 진단이며 kinetic estimator가 아닙니다.

## English

The example starts Na+ and Cl- eight angstroms apart and uses their distance as
the progress coordinate. WESTPA maintains four walkers per bin while
`pmemd.cuda` propagates serial 1 ps implicit-solvent segments.

Run `prepare.py`, `build.sh`, `init.sh`, `run.sh`, and `anal.py` in order. A
normal initialization refuses to overwrite an existing HDF5 file; use
`init.sh --reset` only when intentionally starting over. Each continuation uses
the parent restart and velocities, with an independent positive Langevin seed
derived from `WEST_RAND32`.

The default work manager is `serial` for one GPU. CPU workflow checks can use
`AMBER_ENGINE=sander`, `WESTPA_WORK_MANAGER=processes`, and a positive
`WESTPA_WORKERS` value.

The default configuration runs 20 iterations with a bound-state boundary at
2.6 Å. The target representative is 2.5 Å so it lies inside the `[0, 2.6)`
sink bin rather than on a bin boundary. Tleap uses `PBradii amber6` consistently
with the `igb=1` segment input. Analysis reports total weight, effective walker count, bin occupancy,
sampled distance, and target arrivals. These diagnostics do not constitute a
rate estimate.
