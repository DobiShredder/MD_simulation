# REST3

## 한국어

Chignolin을 ff19SB/TIP3P로 만들고 8-replica solvent-scaled REST3를
실행합니다. Effective temperature는 geometric ladder로 300–450 K를
사용합니다. `states.tsv`에는
`λpp=T0/Tm`, `λpw=sqrt(T0/Tm)`과 다음 κ를 기록합니다.

| Replica | κ |
| ---: | ---: |
| 0–3 | 1.000 |
| 4 | 1.005 |
| 5 | 1.010 |
| 6 | 1.015 |
| 7 | 1.020 |

### 실행

AMBER 26, ParmEd, GROMACS 2026.3, PLUMED 2.10, HREX 지원 MPI GROMACS와
`repex-topology-parser==0.2.2`가 필요합니다.

```bash
python3 -m pip install parmed MDAnalysis numpy
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

`requirements.txt`에는 외부 dependency version을
`repex-topology-parser==0.2.2`로 고정했습니다. 2026년 8월에 배포된 PyPI
wheel은 parser module을 포함하지 않으므로 설치 성공만으로 준비 여부를
판단하지 않습니다. PyPI의 0.2.2 source archive를 풀고 다음처럼 source file
또는 repository root를 지정합니다.

```bash
export REPEX_TOPOLOGY_PARSER_SOURCE=/path/to/repex_topology_parser-0.2.2
```

`generate_rest3.py`는 protein molecule index 0을 hot molecule로 지정하고
TIP3P oxygen type `OW`에 κ scaling을 적용합니다. 고정 κ를 재현하기 위해
각 target state를 2-state `ssrest3` 변환으로 생성합니다. `build.sh`는
replica 0 topology가 base topology와 byte 단위로 같은지 확인하고
water–water 및 ion–water Lennard-Jones parameter가 보존되는지 검사합니다.

Equilibration은 1 ns, production은 10개의 1 ns segment이며 교환은 2 ps마다
시도합니다. 실행 환경 변수와 resume 규칙은 REST2 예제와 같습니다.

### 해석 범위

이 κ schedule은 a99SB-disp를 사용한 IDP 계산에서 보정된 published
schedule을 8개 state에 적용한 것입니다. ff19SB/TIP3P Chignolin에 검증된
parameter가 아닙니다. REST2의 높은 effective temperature에서 나타나는
compaction은 mini-protein folding을 돕기 위해 의도적으로 사용된 특성이므로,
이 예제는 Chignolin에서 REST3가 REST2보다 우수하다고 가정하지 않습니다.

분석은 exchange acceptance, state 방문, occupancy, Rg와 residue 1–10 CA
distance를 TSV로 저장합니다.

- [REST3 원 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10795075/)
- [repex-topology-parser](https://github.com/koreyr/repex_topology_parser)

## English

This example runs eight-state solvent-scaled REST3 for ff19SB/TIP3P Chignolin.
It uses a geometric 300–450 K effective-temperature ladder and the fixed kappa
schedule shown above. Protein molecule 0 is hot, and TIP3P oxygen type `OW`
is the solvent-scaling target.

The build uses `repex-topology-parser==0.2.2`, verifies byte identity of the
base topology, and checks that water–water and ion–water Lennard-Jones
interactions are preserved. Equilibration is 1 ns; production is ten 1 ns
segments with exchanges every 2 ps.

The PyPI wheel inspected in August 2026 does not contain the parser module.
Use the 0.2.2 source archive and point `REPEX_TOPOLOGY_PARSER_SOURCE` to its
root or `src/repex_topology_parser.py`.

The published kappa schedule was calibrated for a99SB-disp IDPs, not validated
for ff19SB/TIP3P Chignolin. REST2 compaction at high effective temperature was
designed to aid mini-protein folding, so this example does not claim that REST3
is superior for Chignolin. Analysis outputs exchange, occupancy, Rg, and
terminal-distance TSV files.
