# AMBER umbrella windows / AMBER umbrella window

## 한국어

Ratchet MD restart를 6–24 Å umbrella window의 seed로 사용합니다. 모든
window는 같은 `system.parm7`을 사용합니다. `windows.tsv`에는 center(Å)와
AMBER NMR-style `rk2=rk3`(kcal mol⁻¹ Å⁻²)을 기록합니다. 다른 engine의 force
constant를 옮길 때는 energy definition을 확인합니다.

각 window의 harmonic restraint는 중심 주변 sampling을 늘리지만 window 밖의
구조를 금지하지는 않습니다. Neighboring histogram이 겹쳐야 PMF offset을
연결할 수 있으므로 center 간격과 force constant는 함께 조정합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `windows.tsv` | Window center(Å)와 force constant를 증가 순서로 정의합니다. |
| `build.sh` | 공통 topology와 ratchet seed를 검증하고 window directory와 `restraint.RST`를 만듭니다. |
| `inputs/restraint.RST.template` | AMBER NMR-style distance restraint의 atom index와 형태를 정의합니다. |
| `run.sh` | 선택한 window 또는 모든 window의 네 stage를 실행합니다. |
| `inputs/continue.in` | 완료된 production restart에서 1 ns를 추가하는 continuation input입니다. |

```bash
cd 1_Simulation/2_US/us
./build.sh
./run.sh --window 1
./run.sh
```

`build.sh`는 `../rmd/work/seeds/`에서 `work/NNN/`을 만듭니다. 기존
window directory가 있으면 종료합니다. 각 window의 계산 순서는 아래와
같습니다.

1. Distance restraint가 활성화된 minimization
2. Protein heavy-atom restraint와 distance restraint를 사용한 200 ps NVT heating
3. Distance restraint를 사용한 100 ps NPT equilibration
4. Distance restraint를 사용한 1 ns NPT production

Minimization, heating 또는 equilibration의 `*.out`과 `*.rst7`이 모두 있으면
해당 stage를 건너뜁니다. 둘 중 일부만 있으면 그 stage를 다시 실행합니다.
기존 `production.out`이 있는 window는 덮어쓰지 않고 시작 전에 중단합니다.
`inputs/continue.in`은 production restart에서 좌표와 velocity를 이어받는
1 ns continuation input입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `iat=2,132` | Terminal Cα pair입니다. Topology가 바뀌면 atom index를 다시 계산합니다. |
| `r2=r3=CENTER` | Flat-bottom 폭이 없는 harmonic center이며 `build.sh`가 `windows.tsv` 값으로 치환합니다. |
| `rk2=rk3=FORCE` | 중심 양쪽의 force constant이며 기본값은 10 kcal mol⁻¹ Å⁻²입니다. |
| `DISANG=restraint.RST` | 모든 minimization·heating·equilibration·production stage에서 window restraint를 읽습니다. |
| `--window N` | 하나의 window만 실행합니다. 생략하면 모든 window를 순서대로 처리합니다. |

Production distance는 `distance.dat`에 1 ps 간격으로 기록됩니다. PMF 계산은
equilibration 제거, time correlation, neighboring histogram overlap과 반복
계산을 포함합니다. 기본 production은 window당 1 ns입니다.

## English

Ordered ratchet-MD restart frames seed windows from 6 to 24 Å. Every window
uses the same topology. `windows.tsv` stores the center in Å and AMBER
NMR-style `rk2=rk3` in kcal mol⁻¹ Å⁻². Check the energy definition before
transferring force constants from another engine.

The harmonic restraint enriches sampling near each center without forbidding
excursions. Center spacing and force constants must produce neighboring
histogram overlap before the PMF offsets can be connected.

`windows.tsv` defines centers and strengths. `build.sh` combines the shared
topology, ordered seeds, and `restraint.RST.template`; `run.sh` executes the
four restrained stages. `iat=2,132` selects the terminal Cα pair,
`r2=r3` sets the center, `rk2=rk3` sets its strength, and `DISANG` keeps the
restraint active. `--window N` limits execution to one window.

`build.sh` creates `work/NNN/` only after validating every seed and
refuses to overwrite an existing build. Each window runs restrained
minimization, 200 ps NVT heating, 100 ps NPT equilibration, and 1 ns NPT
production. A preparation stage is skipped when both its output and restart
exist; an incomplete pair is rerun. A window with an existing `production.out`
is rejected before any production output is overwritten.

`inputs/continue.in` inherits coordinates and velocities from a production
restart. Production distances are written to `distance.dat` every 1 ps. PMF
analysis covers equilibration removal, time correlation, neighboring overlap,
endpoint coverage, and replicate uncertainty. Production is 1 ns per window.
