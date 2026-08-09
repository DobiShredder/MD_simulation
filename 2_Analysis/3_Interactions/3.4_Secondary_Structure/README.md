# Secondary structure / 이차 구조

## 한국어

Cpptraj의 DSSP implementation으로 Chignolin residue별 secondary structure를
분류합니다. Kabsch–Sander hydrogen-bond geometry를 사용하며 integer code
0–7은 None, extended, bridge, 3-10 helix, alpha helix, pi helix, turn, bend에
대응합니다.

```bash
TOPOLOGY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/system.parm7
TRAJECTORY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/production.nc

STRIDE=5 FRAME_INTERVAL_PS=10 \
    ./run.sh "$TOPOLOGY" "$TRAJECTORY"
python3 anal.py
```

`secondary_structure.dat`은 residue–frame assignment,
`secondary_byresidue.dat`은 residue별 population,
`secondary_total.dat`은 frame별 전체 분율을 기록합니다. `anal.py`는
residue-time map과 state fraction을 표시합니다. Cpptraj total output에는
`None` column이 없으므로 Python에서 나머지 분율로 계산합니다.

`secstruct` action에는 stride keyword가 없습니다. `STRIDE=5`는 공통
`run.sh`가 각 `trajin` command의 세 번째 정수인 offset으로 넣습니다. 원본
간격이 10 ps이면 분석 간격은 50 ps입니다. 큰 stride는 계산량을 줄이지만 짧은
secondary-structure transition을 놓칠 수 있습니다.

STRIDE program도 secondary structure assignment에 사용할 수 있습니다.
Cpptraj과 다른 hydrogen-bond 및 assignment 규칙을 사용하므로 두 program의
결과를 같은 label로 바로 합치지 말고 method 차이를 확인합니다. Terminal이나
proline처럼 필요한 backbone amide atom이 없는 residue가 있어도 cpptraj은
정보 메시지를 남기고 나머지 계산을 계속합니다.

## English

Cpptraj's DSSP implementation assigns integer secondary-structure states for
each Chignolin residue and frame. The workflow writes assignments, per-residue
populations, and total fractions; `anal.py` displays a residue-time map and
state fractions. `secstruct` has no stride keyword: the `STRIDE` environment
variable is rendered as the third integer offset of each `trajin` command.
STRIDE is an alternative assignment program, but its definitions differ from
cpptraj DSSP and results should not be merged without checking those method
differences.
