# MM/PBSA

## 한국어

Poisson–Boltzmann equation을 수치적으로 풀어 polar solvation energy를
계산합니다. 같은 frame에서 GB도 함께 계산해 implicit-solvent model에 따른
차이를 확인합니다.

```bash
./run.sh
python3 anal.py
```

Frame, topology와 decomposition 설정은 MM/GBSA tutorial과 같습니다. PB는
`istrng=0.15 M`, `indi=1.0`, `exdi=80.0`, `fillratio=4.0`, `scale=2.0`,
`inp=2`, `radiopt=0`을 사용합니다. `radiopt=0`은 topology의 mbondi2 radii를
사용한다는 뜻입니다.

`anal.py`는 GB와 PB의 energy component, ΔTOTAL running mean, block mean과
residue decomposition을 같은 형식으로 기록합니다. 두 model의 값이 다른 것은
solver failure가 아니며 model dependence를 보여주는 결과입니다.

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

MM/PBSA numerically solves the Poisson–Boltzmann model and runs GB on the same
frames for comparison. PB uses 0.15 M ionic strength, internal/external
dielectrics 1/80, fill ratio 4, scale 2, and topology mbondi2 radii. Differences
between GB and PB report model dependence, not solver error.

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
