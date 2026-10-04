# SASA / 용매 접근 표면적

## 한국어

LCPO algorithm으로 Chignolin 전체 solvent-accessible surface area(SASA)와 각
residue의 기여도를 계산합니다. Probe offset은 AMBER 기본값인 1.4 Å입니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`sasa_total.dat`에는 frame별 protein SASA가, `sasa_byres.dat`에는 residue별
기여도가 Å² 단위로 기록됩니다. `anal.py`는 total time series와 residue별 평균을
표시합니다. Residue 계산에는 `solutemask :1-10`을 사용하므로 각 residue가
분리된 molecule이 아니라 전체 protein에 기여하는 surface를 계산합니다.

다른 system은 `run.sh` 상단의 두 경로와 SASA mask를 수정합니다. LCPO의 부분
selection 기여도는 근사식 때문에 작은 음수가 나올 수 있습니다.
이는 parser failure가 아닙니다. 서로 다른 system이나 ligand-bound state를
비교할 때는 atom mask, radii와 probe offset을 같게 유지합니다.

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

The LCPO algorithm calculates total Chignolin SASA and residue contributions
with the AMBER-default 1.4 Å probe offset. `anal.py` displays the total time
series and mean residue contributions in Å². `solutemask :1-10` evaluates each
residue in the context of the full protein. Small negative contributions can
occur for partial LCPO selections and are not necessarily parser errors. Edit
the two paths and masks for another system.

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
