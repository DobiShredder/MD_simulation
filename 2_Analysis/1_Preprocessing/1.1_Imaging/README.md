# Imaging and centering / Imaging 및 centering

## 한국어

Periodic boundary condition 때문에 분리되어 보이는 molecule을 같은 primary
unit cell에 배치합니다. Chignolin residue `:1-10`을 `autoimage` anchor로
사용하며 protein center of mass와 box center의 거리를 처리 전후로 비교합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 Chignolin conventional-MD output을 직접 읽고
`inputs/cpptraj.in`을 실행합니다. 처리 전후 center를 각각
`center_raw.dat`, `center_imaged.dat`에 기록하고 `imaged.nc`를 생성합니다.
`anal.py`는 두 center-to-box distance를 Å 단위로 표시합니다.

다른 protein을 사용할 때는 `run.sh` 상단의 `topology`와 `trajectory`,
`autoimage anchor :1-10`과 두 `vector ... center` mask를 함께 바꿉니다.

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

## English

This example uses cpptraj `autoimage` to place molecules in a consistent
primary unit cell. Chignolin residues `:1-10` form the anchor. `run.sh` reads
the default simulation output directly and produces `imaged.nc`; `anal.py`
compares protein center-of-mass displacement from the box center. Change the
two paths, anchor, and vector masks together for another system.

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
