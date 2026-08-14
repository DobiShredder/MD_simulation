# Simulation tutorials / 시뮬레이션 튜토리얼

## 한국어

MD input과 실행 template는 이 파트에 있습니다. 후처리와 시각화는
[2_Analysis](../2_Analysis/README.md)에서 다룹니다. 실행 전 atom selection,
force field, 온도·압력과 production length를 대상 system에 맞게 수정합니다.
Protein system의 기본 조합은 ff19SB + TIP3P입니다. KcsA membrane
tutorial만 Lipid21과 OPC를 사용합니다.

대부분의 topology 또는 window `build.sh`는 같은 work directory에서 기존
계산 output을 찾으면 중단합니다. 다른 `WORK_DIR`을 사용하거나 보존 여부를
판단한 뒤 이전 결과를 직접 정리합니다. Runner는 engine이 오류 없이 끝나고
필수 output이 생성된 stage에만 completion marker를 기록합니다. Analysis는
marker가 없는 production segment를 완료된 계산으로 사용하지 않습니다.

| 번호 | 방법 | 포함된 템플릿 |
| --- | --- | --- |
| 1 | [MD](1_MD/README.md) | Chignolin, T4 lysozyme–JZ4, KcsA AMBER MD |
| 2 | [Ratchet MD / US](2_US/README.md) | PLUMED ABMD, 동일-topology seed, umbrella window |
| 3 | [REMD](3_REMD/README.md) | T-REMD, REST2, REST3, REUS, GaREUS |
| 4 | [GaMD](4_GaMD/README.md) | GaMD, LiGaMD3, Pep-GaMD |
| 5 | [FEP](5_FEP/README.md) | RBFE, ABFE |
| 6 | [WE](6_WE/README.md) | WESTPA + AMBER |
| 7 | [MetaD](7_MetaD/README.md) | WT-MetaD, Funnel scaffold, OPES |

`qsub.sh`는 포함하지 않습니다. Cluster용 scheduler script는 각 환경에 맞게
별도로 작성합니다.

## English

Simulation inputs and launch templates are kept here; post-processing lives in
[2_Analysis](../2_Analysis/README.md). Adapt selections, force fields,
thermodynamic settings, and production length to the target system.
Protein templates default to ff19SB with TIP3P. Only the KcsA membrane tutorial
uses Lipid21 and OPC.

Most topology or window `build.sh` scripts stop when the work directory contains
simulation results. Select another `WORK_DIR`, or review and remove the old
results explicitly. Runners write completion markers only after the engine
exits successfully and required outputs exist; analysis does not treat an
unmarked production segment as complete.

The conventional MD examples cover Chignolin, T4 lysozyme–JZ4, and KcsA. The
remaining families provide ratchet MD/umbrella sampling, replica exchange,
GaMD, FEP, weighted ensemble, and MetaD/OPES templates.

Scheduler-specific `qsub.sh` files are not included. Keep queue, account,
module, and path settings in a separate cluster adapter.
