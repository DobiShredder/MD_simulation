# Metadynamics and OPES / Metadynamics 및 OPES

## 한국어

AMBER가 MD를 계산하고 PLUMED가 collective variable(CV)과 bias를 처리합니다.
7.1, 7.3과 7.4는 ff19SB/TIP3P capped alanine dipeptide를 사용합니다.
7.2는 ff19SB/GAFF2/TIP3P trypsin–benzamidine를 사용합니다.

| Directory | Method | Bias 대상 | 상태 파일 |
|---|---|---|---|
| `7.1_WT-MetaD/` | well-tempered MetaD | φ, ψ | `HILLS` |
| `7.2_funnel-MetaD/` | funnel MetaD | trypsin–BEN binding 경로 | `HILLS`, `FUNNEL_GRID` |
| `7.3_OPES_METAD/` | OPES_METAD | φ, ψ | `opes.state`, `KERNELS` |
| `7.4_OPES_EXPANDED/` | multithermal OPES_EXPANDED | potential energy | `opes.state`, `DELTAFS` |

WT-MetaD, Funnel MetaD와 OPES_METAD는 선택한 CV 공간의 barrier를
낮춥니다. Funnel MetaD는 ligand의 solvent 탐색 부피를 cone과 cylinder로
제한합니다. OPES Expanded는
CV 대신 300–500 K multithermal target distribution을 구성합니다. 서로 다른
목표를 가진 method이므로 bias 크기만으로 성능을 비교하지 않습니다.

각 runnable directory에서 `./build.sh`, `./run.sh --dry-run`, `./run.sh`,
`python3 anal.py` 순서로 실행합니다. Production은 1 ns segment 10개입니다.
AMBER restart와 PLUMED bias state가 모두 있어야 다음 segment를 시작합니다.

PLUMED가 연결된 Amber의 `pmemd.cuda`가 기본 engine입니다. AmberTools만 설치한
환경에서는 PLUMED를 포함해 build한 `sander`를 `AMBER_ENGINE=sander`로 지정할
수 있습니다. 설치된 executable이 PLUMED 연동을 지원하는지는 짧은 coupled run으로
확인해야 합니다.

## English

AMBER propagates the MD while PLUMED evaluates the collective variables and
bias. Three examples use an ff19SB/TIP3P capped alanine dipeptide, while Funnel
MetaD uses ff19SB/GAFF2/TIP3P trypsin–benzamidine. They cover well-tempered MetaD on φ/ψ, Funnel MetaD for 3PTB
trypsin–benzamidine, OPES_METAD on φ/ψ, and multithermal OPES_EXPANDED over
300–500 K. Funnel MetaD requires PLUMED's optional `funnel` module.

Run `./build.sh`, `./run.sh --dry-run`, `./run.sh`, and `python3 anal.py` in a
runnable directory. Production consists of ten 1 ns segments. Continuation
requires both the AMBER restart and the method-specific PLUMED state. The default
engine is a PLUMED-enabled `pmemd.cuda`; a PLUMED-enabled `sander` can be selected
with `AMBER_ENGINE=sander`.
