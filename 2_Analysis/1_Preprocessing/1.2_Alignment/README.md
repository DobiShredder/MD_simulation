# Alignment and stripping / 정렬 및 stripping

## 한국어

Imaging한 trajectory를 첫 frame의 backbone에 least-squares fitting하고 solvent와
ion을 제거합니다. Translation과 rotation을 제거한 RMSD는 내부 구조 변화에
집중할 때 사용합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 cpptraj을 실행해 `aligned.nc`, `stripped.parm7`과 `average.pdb`를
만듭니다. `rmsd_before.dat`은 fitting하지 않은 값이고 `rmsd_after.dat`은
`:1-10@CA,C,N` fitting 뒤의 값입니다. `anal.py`는 두 RMSD를 비교합니다.

다른 system은 `run.sh` 상단의 `topology`와 `trajectory`를 수정합니다.
`strip :WAT,Na+,Cl-`는 이 example의 solvent와 ion 이름에 맞춘 mask입니다.
다른 water model이나 ion residue name을 사용할 때는 이 mask도 바꿉니다.
`aligned.nc`와 `stripped.parm7`은 atom 수와 순서가 같으므로 함께 사용합니다.

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

The trajectory is imaged, fitted to the first-frame backbone, and stripped of
water and ions. `run.sh` creates `aligned.nc`, `stripped.parm7`, and an average
structure. `anal.py` compares RMSD before and after fitting. Edit the two paths,
fit mask, and solvent/ion names for another system, and use the stripped
topology with the stripped trajectory.

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
