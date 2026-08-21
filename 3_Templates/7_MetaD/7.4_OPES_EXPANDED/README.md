# OPES_EXPANDED multithermal template

## 한국어

Potential energy `ene`에서 300–500 K multithermal target을 만들고
OPES_EXPANDED가 temperature state의 free-energy offset을 학습합니다. 물리적인 MD
temperature는 300 K이며, bias를 통해 설정 범위의 energy fluctuation을 sampling합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`minimum_temperature_kelvin`과 `maximum_temperature_kelvin`은 base temperature를
포함해야 합니다. 기본 `PACE=500`이며 state grid는 `ECV_MULTITHERMAL`이 자동으로
만듭니다. NPT equilibration 뒤 box를 고정한 NVT production을 실행합니다.

첫 segment는 `DELTAFS`와 `opes.state`를 만들고 이후 segment는 `RESTART`와
`STATE_RFILE=opes.state`로 이어받습니다. PLUMED 2.10은 어느 file에서도 restart할
수 있지만, 이 template는 readable checkpoint인 `opes.state`를 continuation의
단일 기준으로 사용하고 `DELTAFS`는 state별 free-energy estimate와 분석용으로
보존합니다. `anal.py`는 energy, expanded CV, bias 범위와 생성된 state 수를
기록합니다.

이 template는 multithermal expansion입니다. Hamiltonian expansion을 사용하려면
Hamiltonian state 정의와 engine coupling을 별도로 구성해야 합니다.
`download.sh PDB_ID`는 optional source PDB를 내려받습니다. `build.sh`는 NPT
equilibration과 NVT expanded-ensemble input을 만들고, `run.sh`는 state를 이어받아
segment를 실행하며, `anal.py`는 누적 output을 요약합니다.

## English

This template constructs a 300–500 K multithermal target from potential energy.
The physical MD thermostat remains at 300 K while OPES_EXPANDED learns
temperature-state free-energy offsets and biases energy fluctuations. NPT
equilibration is followed by fixed-volume NVT production.

The configured range must contain the base temperature. The first segment
creates `DELTAFS` and `opes.state`. PLUMED 2.10 can restart from either file;
this template consistently reads the readable `opes.state` checkpoint and
retains `DELTAFS` for state free-energy estimates and analysis. Analysis reports
energy, expanded-CV and bias ranges plus the generated state count. Hamiltonian
expansion requires a separate Hamiltonian-state definition and coupling setup.
`download.sh`, `build.sh`, `run.sh`, and `anal.py` retrieve, generate,
propagate, and summarize the configured workflow, respectively.
