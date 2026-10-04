# RMSD, RMSF, and Rg

## 한국어

Chignolin의 backbone RMSD, residue별 RMSF와 radius of gyration(Rg)을 한 번에
계산합니다. RMSD는 첫 frame과 average structure를 각각 reference로 사용합니다.
RMSF는 average structure에 fitting한 좌표에서 계산합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 cpptraj의 두 `run` pass를 사용합니다. 첫 pass에서
`average.pdb`와 `rmsd_first.dat`을 만들고, 두 번째 pass에서
`rmsd_average.dat`, `rmsf_byres.dat`과 `rg.dat`을 만듭니다. `anal.py`는 세
지표를 각각 Å 단위로 표시합니다.

다른 system은 `run.sh` 상단의 두 경로를 수정합니다. RMSD와 RMSF mask는
`:1-10@CA,C,N`이고 Rg는 protein heavy atom에 질량을
적용합니다. Reference와 mask가 바뀌면 값의 의미도 바뀌므로 서로 다른 계산을
비교할 때 같은 definition을 사용합니다. 짧은 trajectory의 안정된 RMSD만으로
구조 ensemble의 수렴을 판단하지 않습니다.

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

This example calculates backbone RMSD against the first frame and the average
structure, residue-level RMSF after fitting, and mass-weighted heavy-atom Rg.
`run.sh` reads the default Chignolin output, uses two cpptraj passes, and writes
the average structure plus four
numeric tables. `anal.py` displays all observables in Å. Keep reference and
mask definitions consistent after editing the two paths for another system.

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
