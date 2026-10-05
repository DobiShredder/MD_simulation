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

### 결과 저장과 재실행

`run.sh`는 빈 temporary directory에서 새 결과를 계산하고 필수 output을
확인한 뒤 `output/`을 교체합니다. 계산 실패나 새 output 누락 시 이전 결과와
log를 유지합니다. 실패한 실행의 log 마지막 부분은 stderr에 출력합니다.

자동 호출되는 `result_generation.py`가 완료한 파일의 hash를
`output/.generation.json`에 기록합니다. `anal.py`는 이 기록을 확인하며,
후처리 파일을 저장하는 경우에도 새 결과를 함께 검증한 뒤 반영합니다.
기록이 없는 과거 결과는 `run.sh`로 다시 생성합니다.

게시가 중단되어 `.output.pending`이 남으면 결과를 소비하거나 다시 게시하지
않습니다. 실행 process가 종료됐는지 확인한 뒤 marker에 적힌 previous/new
directory를 함께 보존하고 검사합니다. 파일을 개별적으로 섞거나 marker만
삭제해서 재실행하지 않습니다.

공개 analysis entry는 자동으로 `writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

Cpptraj's DSSP implementation assigns integer secondary-structure states for
each Chignolin residue and frame. The workflow writes assignments, per-residue
populations, and total fractions; `anal.py` displays a residue-time map and
state fractions. `secstruct` has no stride keyword; use cpptraj `-ya` or the
third `trajin` integer offset for frame sampling. STRIDE is an alternative
assignment program, but its definitions differ from cpptraj DSSP.

### Result storage and reruns

`run.sh` calculates in an empty temporary directory, checks required outputs,
and then replaces `output/`. Calculation failure or missing new outputs leaves
the previous results and logs intact. Recent failed-generation log lines are
printed to stderr.

The automatically called `result_generation.py` records completed file hashes
in `output/.generation.json`. `anal.py` checks this record and, when saving
derived files, validates and publishes them together. Regenerate older results
without a record by running `run.sh`.

If publication stops with `.output.pending` present, readers and publishers
refuse to proceed. Check that the process has ended, then preserve and inspect
both previous/new directories listed in the marker. Do not mix individual files
or remove only the marker to retry.

Public analysis entries automatically use `writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
