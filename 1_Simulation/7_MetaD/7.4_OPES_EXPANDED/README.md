# OPES Expanded Multithermal

## 한국어

OPES_EXPANDED와 `ECV_MULTITHERMAL`을 연결해 300–500 K의 potential-energy
distribution을 한 simulation에서 sampling합니다. Temperature replica를 만드는
REMD와 달리 하나의 walker가 expanded target distribution을 따라갑니다.

```bash
cd 1_Simulation/7_MetaD/7.4_OPES_EXPANDED
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

### Script 역할

| File | 역할 |
|---|---|
| `build.sh` | ff19SB/TIP3P capped alanine system을 생성합니다. |
| `check_topology.py` | `build.sh`가 자동 호출하며 capped peptide atom ordering을 검사합니다. |
| `run.sh` | NPT equilibration 후 fixed-volume multithermal production을 10 × 1 ns로 실행합니다. |
| `anal.py` | potential energy, expanded CV, bias 범위와 `DELTAFS` state 수를 기록합니다. |

### 주요 option

`TEMP=300` K는 실제 thermostat 온도입니다. `TEMP_MIN=300` K와
`TEMP_MAX=500` K는 target multithermal range이며 production은 `ntb=1`,
`ntp=0`으로 box volume을 고정합니다. `PACE=500`은 1 ps마다 OPES estimate를
갱신합니다. 자동 temperature grid를 사용하므로 state 수는 생성된 `DELTAFS`에서
확인합니다.

첫 segment가 `opes.state`와 `DELTAFS`를 만듭니다. Continuation은 두 파일을
복사하고 `STATE_RFILE`과 `RESTART`를 사용합니다. `anal.py`가 출력하는
`ecv.ene`는 expanded CV이며 instantaneous physical temperature가 아닙니다.
Temperature별 observable은 별도 reweighting이 필요합니다.

10 ns는 state 파일과 fixed-volume workflow를 학습하기 위한 길이입니다.
Keyword는 PLUMED 2.10
[`OPES_EXPANDED`](https://www.plumed.org/doc-v2.10/user-doc/html/_o_p_e_s__e_x_p_a_n_d_e_d.html)와
[`ECV_MULTITHERMAL`](https://www.plumed.org/doc-v2.10/user-doc/html/_e_c_v__m_u_l_t_i_t_h_e_r_m_a_l.html)을
기준으로 작성했습니다.

## English

This example combines OPES_EXPANDED with `ECV_MULTITHERMAL` to sample a
300–500 K potential-energy target using one walker. The thermostat remains at
300 K, while production uses a fixed box (`ntb=1`, `ntp=0`). `opes.state` and
`DELTAFS` are both carried into continuation segments. `ecv.ene` is an expanded
CV, not an instantaneous physical temperature; temperature-resolved observables
require separate reweighting. The 10 ns run is a workflow example.
