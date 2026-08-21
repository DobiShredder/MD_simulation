# Replica-exchange templates / Replica-exchange templates

## 한국어

다섯 template는 같은 config 중심 interface를 사용하지만 교환하는 state와 engine이
다릅니다.

| Directory | 교환하는 state | Production interface |
| --- | --- | --- |
| [`3.1_T-REMD`](3.1_T-REMD/README.md) | 실제 temperature | AMBER `-rem 1` |
| [`3.2_REST2`](3.2_REST2/README.md) | REST2-scaled Hamiltonian | PLUMED `-hrex` |
| [`3.3_REST3`](3.3_REST3/README.md) | REST3-scaled Hamiltonian과 κ | PLUMED `-hrex` |
| [`3.4_REUS`](3.4_REUS/README.md) | Reaction-coordinate umbrella state | AMBER `-rem 3` |
| [`3.5_GaREUS`](3.5_GaREUS/README.md) | Umbrella state와 공통 GaMD boost | AMBER `-rem 3` |

T-REMD, REST2와 REST3는 같은 offline temperature predictor 계산식을 사용합니다.
각 leaf에는 이 계산에 필요한 code가 별도로 들어 있습니다. T-REMD는
explicit water를 포함한 전체 atom 수를 사용합니다. REST2/REST3는 water와 ion을
제외한 tempered solute atom 수와 water 0을 사용합니다. `temperature_mode="file"`은
사용자가 제공한 temperature를 그대로 사용합니다. 두 mode 모두 resolved state와
random seed를 `work/states.tsv`에 기록합니다.

각 leaf directory에서 다음 순서로 실행합니다.

```bash
./build.sh INPUT.pdb
./run.sh --dry-run
./run.sh
```

REST2/REST3는 `run.sh --cpus N --gpus N`으로 resource를 override합니다. 생성된
temperature ladder는 근사값이므로 pilot run에서 neighboring acceptance와 round
trip을 확인합니다. REST3의 linear κ schedule도 published example을 일반화한
시작값이며 force field와 system별 검증이 필요합니다.

모든 runner는 `--preparation-only`, `--production-only`와 1-based inclusive
`--segments START-END`를 지원합니다. Exchange production은 선택한 segment의
모든 replica/window를 함께 실행합니다. REUS/GaREUS window subset은 독립적인
exchange ensemble이 아니므로 제공하지 않습니다.

## English

The five templates use the same config-driven interface, while each leaf
contains its own runtime helpers and can be copied independently. T-REMD
exchanges physical temperatures; REST2 and REST3 exchange
scaled Hamiltonians; REUS and GaREUS exchange umbrella states through Amber.

T-REMD, REST2, and REST3 use the same offline temperature-prediction algorithm,
implemented inside each leaf. T-REMD counts
the full solvated system, whereas REST counts the tempered non-water, non-ion
solute and supplies zero waters. Automatic and file-based modes both record the
resolved schedule and random seeds in `work/states.tsv`. T-REMD uses AMBER
`-rem 1`; REST2 and REST3 use PLUMED HREX. Use `--cpus` and `--gpus` to override
REST2/REST3 replica resources. Predictor probabilities and the
default REST3 kappa schedule are starting estimates that require pilot-run
acceptance and round-trip checks.

Every runner supports `--preparation-only`, `--production-only`, and inclusive
1-based `--segments START-END`. Exchange production always includes every
replica or window, so REUS and GaREUS do not expose a production-window subset.
