# Conversion and sampling / 변환 및 frame sampling

## 한국어

선택한 frame을 NetCDF와 DCD로 변환하고 첫 frame을 PDB로 추출합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
```

주요 output은 `sampled.nc`, `sampled.dcd`와 `first_frame.pdb`입니다.
다른 system이나 frame 범위는 `run.sh` 상단의 `topology`, `trajectory`,
`start_frame`, `stop_frame`과 `stride`를 수정합니다.
DCD는 program마다 unit-cell metadata 처리 방식이 다를 수 있으므로 후속 도구가
NetCDF를 지원하면 `sampled.nc`를 우선 사용합니다.

### 결과 저장과 재실행

`run.sh`는 빈 temporary directory에서 새 결과를 계산하고 필수 output을
확인한 뒤 `output/`을 교체합니다. 계산 실패나 새 output 누락 시 이전 결과와
log를 유지합니다. 실패한 실행의 log 마지막 부분은 stderr에 출력합니다.

자동 호출되는 `result_generation.py`가 완료한 파일의 hash를
`output/.generation.json`에 기록합니다. 기록이 없는 과거 결과는 `run.sh`로 다시 생성합니다.

게시가 중단되어 `.output.pending`이 남으면 재실행을 거부합니다.
외부 도구에서도 이 상태의 결과를 소비하지 않습니다. 실행 process가 종료됐는지 확인한 뒤 marker에 적힌 previous/new
directory를 함께 보존하고 검사합니다. 파일을 개별적으로 섞거나 marker만
삭제해서 재실행하지 않습니다.

공개 analysis entry는 자동으로 `writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

Selected frames are converted to NetCDF and DCD, and the first selected frame
is written as PDB. Edit the topology, trajectory, frame limits, and stride at
the top of `run.sh`. Prefer NetCDF when downstream handling of DCD unit-cell
metadata is uncertain.

### Result storage and reruns

`run.sh` calculates in an empty temporary directory, checks required outputs,
and then replaces `output/`. Calculation failure or missing new outputs leaves
the previous results and logs intact. Recent failed-generation log lines are
printed to stderr.

The automatically called `result_generation.py` records completed file hashes
in `output/.generation.json`. Regenerate older results
without a record by running `run.sh`.

If publication stops with `.output.pending` present, reruns refuse to proceed.
External tools must not consume results in this state. Check that the process has ended, then preserve and inspect
both previous/new directories listed in the marker. Do not mix individual files
or remove only the marker to retry.

Public analysis entries automatically use `writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
