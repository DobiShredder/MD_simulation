# Secondary structure / 이차 구조

## 한국어

Cpptraj의 DSSP implementation으로 Chignolin residue별 secondary structure를
분류합니다. Kabsch–Sander hydrogen-bond geometry를 사용하며 integer code
0–7은 None, extended, bridge, 3-10 helix, alpha helix, pi helix, turn, bend에
대응합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`secondary_structure.dat`은 residue–frame assignment,
`secondary_byresidue.dat`은 residue별 population,
`secondary_total.dat`은 frame별 전체 분율을 기록합니다. `anal.py`는
residue-time map과 state fraction을 표시합니다. Cpptraj total output에는
`None` column이 없으므로 Python에서 나머지 분율로 계산합니다.

다른 system은 `run.sh` 상단의 두 경로와 residue mask를 수정합니다.
`secstruct` action에는 stride keyword가 없습니다. Frame을 건너뛰려면
cpptraj command에 `-ya "1 last 5"`를 추가하거나 `trajin`의 세 번째 정수인
offset을 사용합니다. 큰 stride는 짧은 secondary-structure transition을 놓칠
수 있습니다.

STRIDE program도 secondary structure assignment에 사용할 수 있습니다.
Cpptraj과 다른 hydrogen-bond 및 assignment 규칙을 사용하므로 두 program의
결과를 같은 label로 바로 합치지 말고 method 차이를 확인합니다. Terminal이나
proline처럼 필요한 backbone amide atom이 없는 residue가 있어도 cpptraj은
정보 메시지를 남기고 나머지 계산을 계속합니다.

## English

Cpptraj's DSSP implementation assigns integer secondary-structure states for
each Chignolin residue and frame. The workflow writes assignments, per-residue
populations, and total fractions; `anal.py` displays a residue-time map and
state fractions. `secstruct` has no stride keyword; use cpptraj `-ya` or the
third `trajin` integer offset for frame sampling. STRIDE is an alternative
assignment program, but its definitions differ from cpptraj DSSP.
