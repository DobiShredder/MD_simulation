# OPES_METAD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

OPES_METAD는 방문한 위치에 hill을 그대로 누적하지 않습니다. CV sample로
probability distribution을 추정하고 target distribution에 필요한 bias를
갱신합니다. `KERNELS`는 압축된 distribution estimate이고 `opes.state`는 restart에
필요한 adaptive state입니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`cv.dat`의 label과 `collective_variable.arguments`를 함께 수정합니다. 기본
alanine φ/ψ atom 번호는 다른 topology에 적용하지 않습니다. 기본값은
`BARRIER=50 kJ/mol`, `PACE=500`, sigma 0.15 rad이며 CV별 sigma가 필요합니다.

100 ns production은 10 segments로 나뉩니다. 첫 segment가 `KERNELS`와
`opes.state`를 만들고, 이후 segment는 `RESTART`와 `STATE_RFILE`로 두 state를
이어받습니다. Root `COLVAR`도 append됩니다. State file이 하나라도 없으면 다음
segment를 시작하지 않습니다.

`anal.py`는 CV와 bias 범위, final effective sample 수와 kernel 수를 기록합니다.
이 값은 convergence 판정 자체가 아니며 CV coverage와 독립 run을 함께 봅니다.
`download.sh PDB_ID`는 optional source PDB를 내려받습니다. `build.sh`는 topology와
PLUMED input을 만들고 `run.sh`는 `opes.state`를 이어받아 segmented production을
실행합니다.

## English

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

OPES_METAD estimates the sampled CV distribution and updates the bias needed
for a target distribution instead of directly accumulating MetaD hills.
`KERNELS` stores the compressed estimate and `opes.state` stores restartable
adaptive state.

CV labels must match `cv.dat`; the supplied alanine atom numbers are examples.
Defaults are a 50 kJ/mol barrier, 500-step pace, and 0.15 rad sigma per CV. Ten
segments share root-level `KERNELS`, `opes.state`, and `COLVAR`; continuations
use both `RESTART` and `STATE_RFILE`. `download.sh` retrieves an optional source
PDB, while `build.sh`, `run.sh`, and `anal.py` create, propagate, and analyze
the configured workflow.
