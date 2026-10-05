# Hydrogen bonds / 수소 결합

## 한국어

Chignolin 내부 hydrogen bond와 protein–water hydrogen bond를 분리해
계산합니다. Donor–acceptor distance는 3.0 Å 이하, donor–H–acceptor angle은
135° 이상을 사용합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 `ProteinHB`와 `WaterHB` action을 실행합니다.
`protein_hbond_count.dat`과 `water_hbond_count.dat`은 frame별 개수를,
`protein_hbond_average.dat`과 `water_hbond_average.dat`은 interaction별 평균을
기록합니다. `water_bridge.dat`에는 둘 이상의 solute residue를 연결한 water가
기록됩니다. `anal.py`는 count와 protein 내부 occupancy 상위 항목을 표시합니다.

다른 system은 `run.sh` 상단의 두 경로를 수정합니다. `solventdonor :WAT`과
`solventacceptor :WAT@O`는 AMBER의 OPC와 TIP3P가 공유하는 water naming에
맞춘 값입니다. OPC의 `EP`는 hydrogen-bond acceptor로 선택하지 않습니다.
다른 solvent residue나 atom name을 사용하면 두 mask를 바꿉니다. Cutoff를 바꾼
결과는 같은 hydrogen-bond definition을 사용한 결과끼리 비교합니다.

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

The workflow separates intraprotein and protein–water hydrogen bonds using a
3.0 Å distance and 135° angle criterion. It writes per-frame counts,
interaction averages, binary series, and solvent bridges. `anal.py` displays
counts and the most occupied intraprotein bonds. Edit the two paths for another
system. The water masks match the `WAT`/`O` names shared by AMBER OPC and TIP3P;
the OPC `EP` site is not selected as a hydrogen-bond acceptor. Change both masks
if the solvent uses different residue or atom names.

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
