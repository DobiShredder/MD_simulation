# Simulation tutorials / 시뮬레이션 튜토리얼

## 한국어

고정된 MD example과 실행 tutorial은 이 파트에 있습니다. 범용 설정은
[3_Templates](../3_Templates/README.md), 후처리와 시각화는
[2_Analysis](../2_Analysis/README.md)에서 다룹니다. 실행 전 atom selection,
force field, 온도·압력과 production length를 대상 system에 맞게 수정합니다.

| 번호 | 방법 | 포함된 템플릿 |
| --- | --- | --- |
| 1 | [MD](1_MD/README.md) | Chignolin, T4 lysozyme–JZ4, KcsA AMBER MD |
| 2 | [Ratchet MD / US](2_US/README.md) | PLUMED ABMD, 동일-topology seed, umbrella window |
| 3 | [REMD](3_REMD/README.md) | T-REMD, REST2, REST3, REUS, GaREUS |
| 4 | [GaMD](4_GaMD/README.md) | GaMD, LiGaMD3, Pep-GaMD |
| 5 | [FEP](5_FEP/README.md) | RBFE, ABFE |
| 6 | [MetaD](6_MetaD/README.md) | WT-MetaD, Funnel scaffold, OPES |
| 7 | [WE](7_WE/README.md) | WESTPA + AMBER |

### 실행 환경

| 번호 | 기본 engine | GPU와 MPI |
| --- | --- | --- |
| 1 | AMBER `pmemd.cuda` | GPU 1개 |
| 2 | AMBER `pmemd.cuda`. Ratchet MD에는 PLUMED 연동 build가 필요합니다. | GPU 1개 |
| 3 | T-REMD, REUS, GaREUS: `pmemd.cuda.MPI`. REST2, REST3: PLUMED 2.10.2 이상으로 patch한 GROMACS 2024.3 `gmx_mpi` | State 수만큼 MPI rank, GPU |
| 4 | AMBER `pmemd.cuda` | GPU 1개 |
| 5 | AMBER `pmemd.cuda` | GPU 1개 |
| 6 | PLUMED 2.10 연동 AMBER `pmemd.cuda`. Funnel은 `funnel`, OPES는 `opes` module이 필요합니다. | GPU 1개 |
| 7 | WESTPA 2 + AMBER `pmemd.cuda` | GPU |

Build 조건과 실행 option은 각 family README에 있습니다. `pmemd.cuda` 없이
`sander`로 짧게 test하는 조건은 [루트 README](../README.md)를 참고합니다.

Protein system의 기본 조합은 ff19SB + OPC입니다. KcsA membrane tutorial은
같은 protein/water 조합에 Lipid21을 추가합니다. OPC의 massless EP를 포함한
4-site water topology와 OPC용 ion parameter는 `leaprc.water.opc`가 불러옵니다.

각 `run.sh`는 `--dry-run`을 지원합니다. Build output을 읽어 실행할 command를
표시하지만 engine을 실행하거나 `work/`의 파일을 변경하지 않습니다.

완료한 stage의 재사용, partial output 처리, 실패 후 재실행과 동시 실행 보호는
[GUIDE.md 부록](../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

`qsub.sh`는 포함하지 않습니다. Cluster용 scheduler script는 각 환경에 맞게
별도로 작성합니다.

## English

Fixed simulation examples and launch tutorials are kept here. Generalized
configuration lives in [3_Templates](../3_Templates/README.md), and
post-processing lives in [2_Analysis](../2_Analysis/README.md). Adapt atom
selections, force field, temperature, pressure, and production length to the
target system before running.

| No. | Method | Included templates |
| --- | --- | --- |
| 1 | [MD](1_MD/README.md) | Chignolin, T4 lysozyme–JZ4, KcsA AMBER MD |
| 2 | [Ratchet MD / US](2_US/README.md) | PLUMED ABMD, same-topology seeds, umbrella windows |
| 3 | [REMD](3_REMD/README.md) | T-REMD, REST2, REST3, REUS, GaREUS |
| 4 | [GaMD](4_GaMD/README.md) | GaMD, LiGaMD3, Pep-GaMD |
| 5 | [FEP](5_FEP/README.md) | RBFE, ABFE |
| 6 | [MetaD](6_MetaD/README.md) | WT-MetaD, Funnel scaffold, OPES |
| 7 | [WE](7_WE/README.md) | WESTPA + AMBER |

### Runtime requirements

| No. | Default engine | GPU and MPI |
| --- | --- | --- |
| 1 | AMBER `pmemd.cuda` | One GPU |
| 2 | AMBER `pmemd.cuda`; ratchet MD needs a PLUMED-enabled build | One GPU |
| 3 | T-REMD, REUS, GaREUS: `pmemd.cuda.MPI`. REST2, REST3: GROMACS 2024.3 `gmx_mpi` patched with PLUMED 2.10.2 or newer | One MPI rank per state, GPU |
| 4 | AMBER `pmemd.cuda` | One GPU |
| 5 | AMBER `pmemd.cuda` | One GPU |
| 6 | PLUMED 2.10-enabled AMBER `pmemd.cuda`; Funnel needs the `funnel` module and OPES the `opes` module | One GPU |
| 7 | WESTPA 2 + AMBER `pmemd.cuda` | GPU |

Build requirements and run options are in each family README. See the
[root README](../README.md) for short `sander` tests without `pmemd.cuda`.

Protein tutorials use ff19SB with OPC. The KcsA membrane tutorial adds Lipid21
to the same protein/water combination. `leaprc.water.opc` loads the four-site
OPC water topology, including its massless EP, and the matching ion parameters.

Every `run.sh` supports `--dry-run`. It reads the build outputs and prints the
commands without launching an engine or modifying files under `work/`.

Reuse of completed stages, partial outputs, reruns after a failure, and
concurrent-run protection are described in [GUIDE.md appendix](../GUIDE.md#4-appendix-run-state-and-recovery).

Scheduler-specific `qsub.sh` files are not included. Keep queue, account,
module, and path settings in a separate cluster adapter.
