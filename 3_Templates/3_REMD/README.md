# Replica-exchange templates / Replica-exchange templates

## 한국어

T-REMD, REST2, REST3, REUS와 GaREUS는 최소 2개·짝수 replica만 지원합니다. 일반 US의 독립 window에는 이 제한을 적용하지 않습니다.

다섯 template는 같은 config 중심 interface를 사용하지만 교환하는 state와 engine이
다릅니다.

| Directory | 교환하는 state | Production interface |
| --- | --- | --- |
| [`3.1_T-REMD`](3.1_T-REMD/README.md) | 실제 temperature | AMBER `-rem 1` |
| [`3.2_REST2`](3.2_REST2/README.md) | REST2-scaled Hamiltonian | PLUMED `-hrex` |
| [`3.3_REST3`](3.3_REST3/README.md) | REST3-scaled Hamiltonian과 κ | PLUMED `-hrex` |
| [`3.4_REUS`](3.4_REUS/README.md) | Reaction-coordinate umbrella state | AMBER `-rem 3` |
| [`3.5_GaREUS`](3.5_GaREUS/README.md) | Umbrella state와 공통 GaMD boost | AMBER `-rem 3` |

### REST2/REST3 GROMACS–PLUMED build

REST2와 REST3 production에는 PLUMED 2.10.2 이상으로 patch한
`GROMACS 2024.3` external-MPI build가 필요합니다. 서로 다른 scaled topology를
`-hrex`로 교차 평가하는 경로는 PLUMED의 GROMACS 2024 patch에만 있습니다.
GROMACS 2025/2026 patch와 built-in PLUMED interface에는 이 경로가 없습니다.
PLUMED 2.10.0과 2.10.1의 GROMACS 2024 patch는 swapped coordinate의 energy를
잘못 계산해 exchange가 거의 accept되지 않으며, 2.10.2에서 수정되었습니다
([PLUMED issue #1326](https://github.com/plumed/plumed2/issues/1326)).

GROMACS source root에서 PLUMED patch를 적용하고 external MPI로 build한 뒤
option과 PLUMED patch version을 확인합니다.

```bash
plumed patch -p -e gromacs-2024.3
gmx_mpi mdrun -h 2>&1 | grep -E -- '-hrex|-plumed'
gmx_mpi --version | grep 'GROMACS version'
```

Version은 `2024.3-plumed_2.10.2`처럼 표시됩니다. REST2/REST3 runner도
production 시작 전에 `-hrex`와 이 PLUMED version(2.10.2 이상)을 검사합니다.
GROMACS 2024.6처럼 다른 2024 bugfix release에 2024.3 patch를 적용하는 조합과
실제 GPU/external-MPI HREX 실행은 미검증이므로 설치 환경에서 짧은 pilot run으로
확인합니다.

T-REMD, REST2와 REST3는 같은 offline temperature predictor 계산식을 사용합니다.
각 leaf에는 이 계산에 필요한 code가 별도로 들어 있습니다. T-REMD는
explicit water를 포함한 전체 atom 수를 사용합니다. REST2/REST3는 water와 ion을
제외한 tempered solute atom 수와 water 0을 사용합니다. `temperature_mode="file"`은
사용자가 제공한 temperature를 그대로 사용합니다. 두 mode 모두 resolved state와
random seed를 `work/states.tsv`에 기록합니다.

`temperature_mode`의 `auto`/`file` 선택은 T-REMD, REST2와 REST3에만 있습니다.
REST3는 κ의 `linear`/`file` 선택을 추가합니다. REUS와 GaREUS는
`windows_file`에 적힌 umbrella state를 항상 사용하며 이를 mode로 선택하지
않습니다. 허용값과 file validation은 각 leaf README에 정리되어 있습니다.

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

T-REMD, REST2, REST3, REUS and GaREUS support only even replica counts of at least two. Independent windows in ordinary US are outside this restriction.

### REST2/REST3 GROMACS–PLUMED build

REST2 and REST3 production require an external-MPI build of GROMACS 2024.3
patched with PLUMED 2.10.2 or later. Only the PLUMED patch for GROMACS 2024
provides the `-hrex` path that cross-evaluates differently scaled topologies;
the GROMACS 2025/2026 patches and the built-in PLUMED interface do not. The
GROMACS 2024 patch in PLUMED 2.10.0 and 2.10.1 computes a wrong
swapped-coordinate energy, so exchanges are almost never accepted; PLUMED
2.10.2 fixes this ([PLUMED issue #1326](https://github.com/plumed/plumed2/issues/1326)).

From the GROMACS source root, apply the PLUMED patch, build with external MPI,
and check the options and the PLUMED patch version:

```bash
plumed patch -p -e gromacs-2024.3
gmx_mpi mdrun -h 2>&1 | grep -E -- '-hrex|-plumed'
gmx_mpi --version | grep 'GROMACS version'
```

The version reads like `2024.3-plumed_2.10.2`. The REST2 and REST3 runners
repeat the `-hrex` check and require PLUMED 2.10.2 or later before production.
Applying the 2024.3 patch to another 2024 bugfix release such as 2024.6, and an
actual GPU/external-MPI HREX run, are unverified; check them with a short pilot
run in the target installation.

The five templates use the same config-driven interface, while each leaf
contains its own runtime helpers. T-REMD
exchanges physical temperatures; REST2 and REST3 exchange
scaled Hamiltonians; REUS and GaREUS exchange umbrella states through Amber.

T-REMD, REST2, and REST3 use the same offline temperature-prediction algorithm,
implemented inside each leaf. T-REMD counts
the full solvated system, whereas REST counts the tempered non-water, non-ion
solute and supplies zero waters. Automatic and file-based modes both record the
resolved schedule and random seeds in `work/states.tsv`. The `auto`/`file`
`temperature_mode` choice applies only to T-REMD, REST2, and REST3. REST3
additionally provides `linear`/`file` κ selection. REUS and GaREUS always read
the umbrella states listed in `windows_file`; this is not a mode switch. Each
leaf README gives the accepted values and file validation. T-REMD uses AMBER
`-rem 1`; REST2 and REST3 use PLUMED HREX. Use `--cpus` and `--gpus` to override
REST2/REST3 replica resources. Predictor probabilities and the
default REST3 kappa schedule are starting estimates that require pilot-run
acceptance and round-trip checks.

Every runner supports `--preparation-only`, `--production-only`, and inclusive
1-based `--segments START-END`. Exchange production always includes every
replica or window, so REUS and GaREUS do not expose a production-window subset.
