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

### REST2/REST3 GROMACS–PLUMED build

REST2와 REST3 production에는 `GROMACS 2024.3` 또는 `2024.6`에 PLUMED
2.10의 GROMACS 2024.3 patch와 이 directory의 HREX energy correction을
차례로 적용한 external-MPI build가 필요합니다. PLUMED 2.10 원본 patch는
swapped coordinate의 energy workload를 준비하지 않아 exchange energy를
잘못 계산합니다. GROMACS 2025 patch와 built-in PLUMED interface에는 서로
다른 scaled topology를 교차 평가하는 `-hrex` 경로가 없습니다.

PLUMED patch를 적용한 GROMACS source root에서 먼저 correction 적용 가능 여부를
확인한 뒤 적용합니다.

```bash
plumed patch -p
patch --dry-run -p1 < /path/to/3_Templates/3_REMD/patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch
patch -p1 < /path/to/3_Templates/3_REMD/patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch
```

GROMACS를 external-MPI로 build한 뒤 option과 correction marker를 확인합니다.

```bash
gmx_mpi mdrun -h 2>&1 | grep -E -- '-hrex|-plumed|HREX_WORKLOAD_FIX_1'
```

REST2/REST3 runner도 production 시작 전에 `-hrex`와
`HREX_WORKLOAD_FIX_1`을 검사합니다. Patch 적용은 GROMACS 2024.3과 2024.6
source에서 확인했고, 수정된 GROMACS 2024.6 CPU source compilation까지
검증했습니다. GPU/external-MPI HREX는 설치 환경에서 짧은 pilot run으로 별도
검증해야 합니다. `patch --dry-run`이 실패하면 강제로 적용하지 말고 GROMACS와
PLUMED source version을 확인합니다.

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

### REST2/REST3 GROMACS–PLUMED build

REST2 and REST3 production require an external-MPI build of GROMACS 2024.3
or 2024.6. Apply the PLUMED 2.10 patch for GROMACS 2024.3 first, followed by
the HREX energy correction provided in this directory. The upstream PLUMED
2.10 patch does not prepare the swapped-coordinate energy workload and can
therefore compute an invalid exchange energy. The GROMACS 2025 patch and the
built-in PLUMED interface do not provide the arbitrary-topology `-hrex` path
required here.

From the GROMACS source root, check and apply the correction after running the
PLUMED patch:

```bash
plumed patch -p
patch --dry-run -p1 < /path/to/3_Templates/3_REMD/patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch
patch -p1 < /path/to/3_Templates/3_REMD/patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch
```

After building GROMACS with external MPI, verify the options and marker:

```bash
gmx_mpi mdrun -h 2>&1 | grep -E -- '-hrex|-plumed|HREX_WORKLOAD_FIX_1'
```

The REST2 and REST3 runners repeat the `-hrex` and `HREX_WORKLOAD_FIX_1`
checks before production. Patch application was checked against GROMACS
2024.3 and 2024.6 source, including CPU compilation of the corrected GROMACS
2024.6 source. Validate GPU/external-MPI HREX with a short pilot run in the
target installation. Do not force the patch if `patch --dry-run` fails; check
the GROMACS and PLUMED source versions instead.

The five templates use the same config-driven interface, while each leaf
contains its own runtime helpers. A copied REST2 or REST3 leaf also needs this
family's `patches/` directory when preparing GROMACS. T-REMD
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
