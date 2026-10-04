# Geometry / 거리·각도·이면각

## 한국어

원자 selection으로 정의한 distance, minimum distance, angle과 backbone
dihedral을 계산합니다. Chignolin의 terminal Cα distance와 residue 1–5–10 Cα
angle은 전체 fold의 간단한 collective variable로 사용합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`geometry.dat`에는 `:1@CA`–`:10@CA` distance, residue 1–5와 6–10 heavy atom
사이의 minimum distance, Cα angle이 기록됩니다. `phi_psi.dat`에는 residue
2–9의 φ/ψ가 들어갑니다. `anal.py`는 distance와 angle time series 및 residue
5 Ramachandran scatter를 표시합니다. Distance는 Å, angle과 dihedral은 degree
단위입니다.

다른 system은 `run.sh` 상단의 두 경로를 수정합니다. Atom mask는 물리적으로
추적하려는 group을 반영해야 합니다. Residue 번호만
그대로 둔 채 다른 protein에 적용하지 않습니다. Imaging은 계산 전에 수행하지만
원하는 molecule이 같은 image에 놓였는지도 확인합니다.

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

The example calculates terminal Cα distance, minimum heavy-atom distance
between two residue groups, a three-Cα angle, and backbone φ/ψ. `anal.py`
shows the time series and a residue-5 Ramachandran scatter. Distances use Å;
angles and dihedrals use degrees. Edit the two paths and redesign the atom masks
rather than copying the Chignolin residue numbers to another protein.

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
