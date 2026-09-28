# GaREUS template

## 한국어

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다. Replica는 공통 `work/system.parm7`과 `work/system.rst7`을 직접 참조하며 replica별 engine input, bias, seed와 restart는 각 directory에 남습니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

REUS의 umbrella-state 교환에 system 전체의 dual-boost GaMD를 결합합니다.
한 reference replica에서 만든 `gamd-restart.dat`를 모든 window에 복사하므로
production 시작 시 같은 boost parameter를 사용합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

Reaction-coordinate mask, center, force와 exchange interval은 REUS와 같습니다.
GaMD statistics 길이와 `sigma0=6 kcal/mol`은 `[gamd]`에 기록됩니다. Build는
REUS와 같은 window/restraint generator에 GaMD parameter-preparation input을
추가합니다. Run은 GaMD state continuation과 AMBER `-rem 3` exchange command를
조합합니다. MD restart, window restraint와 GaMD state 중 하나라도 partial이면
production을 덮어쓰지 않습니다.
`download.sh PDB_ID`는 source PDB를 내려받고 `build.sh`는 topology, window와
GaMD input을 생성합니다.

기본 production은 window당 200 ns입니다. 2 fs timestep과 1000-step exchange
interval에서 `nstlim=1000`, `numexchg=100000`으로 생성됩니다.
기본 20개 window는 6–25 Å이며 replica 009에서 공통 GaMD state를 준비합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Window equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | GaMD exchange production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Window별 seed를 무작위로 만들거나 정수에서 파생합니다. |

`windows_file`은 항상 명시적인 center 목록을 읽으며 `auto`/`file` mode가
아닙니다. Blank line과 `#`로 시작하는 comment line을 제외하고 각 행에는 center
하나만 적습니다. Center 목록은 비어 있지 않고 중복 없이 오름차순이어야 합니다.
각 행이 한 exchange state가 되고 최종 mapping은 `work/states.tsv`에 기록됩니다.

## English

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; it is not a separate entry point.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained. Replicas reference the shared `work/system.parm7` and `work/system.rst7` directly, while replica-specific engine inputs, bias, seeds, and restart files remain in each directory.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets GaMD exchange-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random window seeds or derives them from the integer. |

`windows_file` always supplies an explicit center list and is not an
`auto`/`file` mode. After blank lines and full-line `#` comments are skipped,
each row must contain exactly one center. The list must be nonempty, unique,
and increasing. Each row becomes one exchange state, and the final mapping is
written to `work/states.tsv`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

GaREUS combines umbrella-state exchange with a common system-wide dual GaMD
boost. One reference replica prepares `gamd-restart.dat`, which is copied to
all windows before production. The build extends the shared REUS window
generator with GaMD preparation input, and the run combines GaMD state
continuation with the AMBER `-rem 3` exchange command. Partial production,
restraint, or GaMD state is not overwritten. `download.sh`
retrieves a source PDB and `build.sh` creates the topology, windows, and GaMD
inputs. The default is 200 ns
per window, rendered as `nstlim=1000` and `numexchg=100000` at 2 fs. The
default has 20 windows from 6 to 25 Å and prepares the shared GaMD state in
replica 009.
