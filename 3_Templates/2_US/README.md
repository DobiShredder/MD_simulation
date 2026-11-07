# Umbrella sampling template

## 한국어

Reaction coordinate의 각 window를 독립적으로 sampling합니다. PLUMED
ABMD ratchet MD로 target-directed trajectory를 만들고 window center를 처음
통과하는 frame을 seed로 선택한 뒤, 같은 topology와 서로 다른
harmonic restraint를 사용합니다.

[`2.1_US`](2.1_US/README.md)에서 topology build, rMD, seed 추출, window build와
simulation을 순서대로 실행합니다. Reaction-coordinate atom mask와 center 목록은
system별 input입니다. Window center와 force constant는 `config.toml`의
`umbrella.centers`, `umbrella.force_constants` 배열을 항상 사용하며, `auto`/`file`
mode를 선택하는 option은 없습니다.

`us/run.sh --window N`과 `--windows START-END`는 1-based index를 사용하며 범위는
inclusive입니다. `--preparation-only`와 `--production-only`로 선택한 window의
실행 stage를 나눌 수 있습니다.

### 준비 사항

| 필요한 것 | 사용하는 곳 |
| --- | --- |
| Bash 4.4 이상, `curl`, Python 3 | `download.sh`, `rmd/anal.py`와 자동 호출되는 `helpers/` |
| `2.1_US/requirements.txt` | Python 3.11 미만의 `tomli`, NumPy, ParmEd. ParmEd는 atom mask를 atom index로 바꿉니다. |
| AmberTools 26 `tleap`, `cpptraj` | `build.sh`, `rmd/anal.py` |
| Amber 26 `pmemd.cuda`와 NVIDIA GPU | `rmd/run.sh`와 `us/run.sh`가 허용하는 유일한 engine입니다. `rmd/run.sh`는 `plumed=1`을 쓰므로 PLUMED와 연결된 build가 필요합니다. |

## English

Each window independently samples one region of a reaction coordinate. PLUMED
ABMD ratchet MD generates the directed pathway, and ordered first-crossing
frames seed simulations with one shared topology and window-specific harmonic
restraints.

[`2.1_US`](2.1_US/README.md) runs the topology build, rMD, seed extraction,
window build, and simulation in order. The reaction-coordinate atom masks and the
center list are system-specific inputs. Window centers and force constants
always come from the `umbrella.centers` and `umbrella.force_constants` arrays in
`config.toml`; there is no `auto`/`file` mode switch.

`us/run.sh --window N` and the inclusive `--windows START-END` range both use
1-based indices. The selected windows can be split into preparation and
production with `--preparation-only` and `--production-only`.

### Prerequisites

| Requirement | Used by |
| --- | --- |
| Bash 4.4 or newer, `curl`, Python 3 | `download.sh`, `rmd/anal.py`, and the automatically called `helpers/` |
| `2.1_US/requirements.txt` | `tomli` on Python older than 3.11, NumPy, and ParmEd; ParmEd converts atom masks to atom indices. |
| AmberTools 26 `tleap`, `cpptraj` | `build.sh`, `rmd/anal.py` |
| Amber 26 `pmemd.cuda` and an NVIDIA GPU | The only engine accepted by `rmd/run.sh` and `us/run.sh`. `rmd/run.sh` uses `plumed=1`, so it needs a PLUMED-linked build. |
