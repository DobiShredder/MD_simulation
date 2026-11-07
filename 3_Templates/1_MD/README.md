# Conventional MD templates / Conventional MD template

## 한국어

Soluble protein, protein–ligand와 membrane protein은 preparation 과정이 달라
별도 template로 구성합니다. System 종류는 leaf directory로 선택하며 별도 config
mode가 아닙니다. 각 directory의 README에서 해당 system에 허용되는 config 선택값을
확인합니다.

| Directory | 추가 input |
| --- | --- |
| `1.1_Soluble_Protein` | Build-ready protein PDB |
| `1.2_Protein_Ligand` | Complex PDB, RESP/GAFF2 MOL2와 frcmod |
| `1.3_Membrane_Protein` | Oriented protein PDB와 equilibrated Lipid21 bilayer patches |

세 `run.sh`는 `--preparation-only`, `--production-only`와 1-based inclusive
`--segments START-END`를 지원합니다. Segment 2 이후부터 시작하려면 직전
segment의 completion marker와 restart file이 있어야 합니다. 공통 build와 stage
설정은 [template 안내](../README.md)에 정리되어 있습니다.

### 준비 사항

| 필요한 것 | 사용하는 곳 |
| --- | --- |
| Bash 4.4 이상, `curl`, Python 3 | `download.sh`와 자동 호출되는 `helpers/` |
| Leaf의 `requirements.txt` | 1.1은 Python 3.11 미만에서 `tomli`만 필요합니다. 1.2와 1.3은 NumPy와 ParmEd를 추가로 설치합니다. |
| AmberTools 26 `tleap` | 모든 `build.sh` |
| `pmemd.cuda`(기본), `pmemd` 또는 `sander` | `run.sh`. `run.engine` 또는 `AMBER_ENGINE`으로 고릅니다. `pmemd.cuda`는 Amber 26과 NVIDIA GPU가 필요합니다. |

1.2는 외부에서 만든 RESP charge MOL2와 frcmod를, 1.3은 equilibrated Lipid21 bilayer
patch를 추가로 준비합니다. 결과 판단 기준은 tutorial의
[conventional MD README](../../1_Simulation/1_MD/README.md#결과-판단)와 같습니다.

### 자주 생기는 문제

세 leaf의 `build.sh`와 `run.sh`가 공통으로 출력하는 message입니다. 남은 파일
처리는 [GUIDE.md 부록](../../GUIDE.md#4-부록-실행-상태와-복구)을 따릅니다.

| Message | 조치 |
| --- | --- |
| `Config error: ...` | `config.toml`의 해당 key를 고친 뒤 새 `WORK_DIR`에서 다시 build합니다. |
| `Build output already exists and was retained` | 다른 `WORK_DIR`을 지정하거나 기존 `work`를 옮긴 뒤 build합니다. |
| `AMBER engine not found` | Amber 환경을 불러오거나 `AMBER_ENGINE`에 executable을 지정합니다. |
| `Run preflight: ... Run ./build.sh first.` | 같은 `WORK_DIR`로 `build.sh`를 먼저 실행합니다. |
| `<stage> failed in <directory>; engine output: ...` | 함께 출력된 마지막 20줄과 같은 directory의 `engine.<stage>.log`를 봅니다. |
| `Previous production segment is incomplete` | `--segments`의 시작 segment 직전까지 먼저 완료합니다. |

## English

Soluble-protein, protein–ligand, and membrane-protein systems use different
preparation workflows and are kept as separate templates. The system type is
selected by the leaf directory, not by a config mode. Each leaf README lists the
config choices supported for that system.

| Directory | Additional input |
| --- | --- |
| `1.1_Soluble_Protein` | Build-ready protein PDB |
| `1.2_Protein_Ligand` | Complex PDB, reviewed RESP/GAFF2 MOL2 and frcmod |
| `1.3_Membrane_Protein` | Oriented protein PDB and equilibrated Lipid21 bilayer patches |

All three runners support `--preparation-only`, `--production-only`, and
inclusive 1-based `--segments START-END`. Starting after segment 1 requires the
preceding completion marker and restart. See the [template guide](../README.md)
for shared build and stage controls.

### Prerequisites

| Requirement | Used by |
| --- | --- |
| Bash 4.4 or newer, `curl`, Python 3 | `download.sh` and the automatically called `helpers/` |
| The leaf `requirements.txt` | 1.1 needs only `tomli` on Python older than 3.11; 1.2 and 1.3 add NumPy and ParmEd. |
| AmberTools 26 `tleap` | Every `build.sh` |
| `pmemd.cuda` (default), `pmemd`, or `sander` | `run.sh`, selected by `run.engine` or `AMBER_ENGINE`. `pmemd.cuda` needs Amber 26 and an NVIDIA GPU. |

1.2 also needs an externally prepared RESP-charge MOL2 and frcmod, and 1.3
needs equilibrated Lipid21 bilayer patches. Judge the results with the same
criteria as the tutorial
[conventional-MD README](../../1_Simulation/1_MD/README.md#judging-the-result).

### Common problems

These messages are shared by the `build.sh` and `run.sh` of all three leaves.
Handle retained files as described in the
[GUIDE.md appendix](../../GUIDE.md#4-appendix-run-state-and-recovery).

| Message | Action |
| --- | --- |
| `Config error: ...` | Fix that key in `config.toml` and build again in a new `WORK_DIR`. |
| `Build output already exists and was retained` | Set another `WORK_DIR` or move the existing `work` aside before building. |
| `AMBER engine not found` | Load the Amber environment or set `AMBER_ENGINE` to an executable. |
| `Run preflight: ... Run ./build.sh first.` | Run `build.sh` first with the same `WORK_DIR`. |
| `<stage> failed in <directory>; engine output: ...` | Read the last 20 lines printed with it and `engine.<stage>.log` in the same directory. |
| `Previous production segment is incomplete` | Complete the segments before the `--segments` start first. |
