# GaREUS reweighting / GaREUS reweighting 분석

## 한국어

[`3.5_GaREUS`](../../../1_Simulation/3_REMD/3.5_GaREUS/README.md)의 terminal
Cα distance PMF를 two-step reweighting으로 계산합니다. MBAR로 REUS
restraint를 먼저 제거한 뒤, GaMD boost를 2차 cumulant expansion으로
제거합니다.

GaREUS production을 완료한 다음 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

PyMBAR 4가 필요합니다.

```bash
conda activate ambertools26
conda install -c conda-forge "pymbar>=4,<5"
```

`run.sh`는 20개 window의 `restraint.production.dat`과
`gamd.production.log`를 읽습니다. 각 window에서 distance와 dual-boost
record 수가 같지 않으면 중단합니다. AMBER GaMD log 형식이 달라지면
`prepare.py`의 `read_boost()`에서 component column을 확인합니다.

Input과 output 경로는 `prepare.py`의 `SIMULATION_WORK`와 `OUTPUT_DIR`에서
설정합니다. `run.sh`는 이 script를 호출하며 input 검사와 결과 경로 출력도
`prepare.py`가 처리합니다.

`anal.py`는 각 frame을 모든 umbrella Hamiltonian에서 평가하고, bias가 없는
sample weight를 PyMBAR로 계산합니다. 이 단계가 제거하는 것은 REUS bias뿐이며
GaMD bias는 남아 있습니다. 각 distance bin에서 MBAR weight를 사용해 boost의
평균과 분산을 구한 뒤 다음 2차 cumulant approximation을 적용합니다.

\[
\ln \langle e^{\beta\Delta U}\rangle_\xi
\simeq \beta\langle\Delta U\rangle_\xi
+\frac{\beta^2}{2}\operatorname{Var}_\xi(\Delta U)
\]

| Output | 내용 |
| --- | --- |
| `output/pmf.tsv` | REUS bias만 제거한 PMF와 GaMD bias까지 제거한 1D PMF |
| `output/mbar_weights.tsv` | Window와 frame별 unbiased MBAR weight |
| `output/overlap_matrix.tsv` | Sampled umbrella state 사이의 MBAR overlap matrix |
| `output/mbar_diagnostics.tsv` | PyMBAR version, weight normalization과 effective sample size |

이 계산은 모든 replica에 같은 GaMD parameter가 적용되고 umbrella restraint만
다르다는 조건을 사용합니다. Simulation README의 shared
`gamd-restart.dat` workflow를 바꾸면 MBAR reduced potential도 함께 수정해야
합니다.

1 ns 결과와 2차 cumulant approximation은 수렴된 정량 free energy를
보장하지 않습니다. Overlap, effective sample size, boost distribution의
Gaussian 성질, bin width와 independent run을 함께 확인합니다. Bootstrap,
2D PMF와 kinetic reweighting은 포함하지 않습니다.

Tutorial의 단일 production output을 읽으며, 생성 TSV의 `segment` column은 1입니다. Template의 segmented output은 지원하지 않습니다.

### 결과 저장과 재실행

`prepare.py`는 모든 window의 series와 `summary.tsv`를 temporary directory에
만든 뒤 `output/`을 교체합니다. 뒤 window에서 실패해도 이전 결과를 유지합니다.
완료한 파일의 hash는 `output/.generation.json`에 기록합니다.

`anal.py`는 이 기록과 일치하는 series/summary만 읽습니다. 검증한 input을
별도 generation에 복사하고, PMF와 진단 파일이 모두 작성된 뒤 함께 반영합니다.
Preparation을 성공적으로 다시 실행하면 이전 PMF는 새 series와 섞이지 않도록
교체됩니다. 완료 기록이 없는 과거 결과는 `run.sh`로 다시 생성합니다.

게시가 중단되어 `.output.pending`이 남으면 preparation과 consumer가 중단합니다.
실행 process가 종료됐는지 확인한 뒤 marker에 적힌 previous/new directory를
보존하고 검사합니다. 여러 파일의 교체를 하나의 atomic write로 취급하지 않습니다.

공개 analysis entry는 자동으로 `writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

This example calculates a one-dimensional terminal-Cα-distance PMF from the
matching GaREUS simulation. PyMBAR first assigns snapshot probabilities after
removing the REUS umbrella restraints. Weighted, bin-local boost means and
variances are then used for a second-order cumulant approximation that removes
the GaMD bias.

Run `./run.sh` to pair distance and dual-boost records for all 20 windows, then
run `python3 anal.py`. The outputs include the PMF before and after GaMD
reweighting, per-frame MBAR weights, the state-overlap matrix, and weight
diagnostics.

Set input and output paths with `SIMULATION_WORK` and `OUTPUT_DIR` in `prepare.py`.
`run.sh` calls this script, which also checks inputs and reports output paths.

The reduced-potential construction assumes that all replicas share the same
GaMD parameters and differ only in their umbrella restraints. The 1 ns result
is a workflow exercise rather than a converged quantitative free energy.
Bootstrap uncertainty, two-dimensional PMFs, and kinetic reweighting are not
included.

### Result storage and reruns

`prepare.py` creates every window series and `summary.tsv` in a temporary
directory before replacing `output/`. Failure in a later window preserves the
previous results. Completed file hashes are recorded in `output/.generation.json`.

`anal.py` reads only series/summary files matching that record. It copies checked
inputs to a separate generation and publishes the PMF and diagnostics only after
all files have been written. A successful preparation rerun replaces the old PMF
along with its inputs rather than mixing it with new series. Regenerate older
results without a completion record by running `run.sh`.

If publication stops with `.output.pending` present, preparation and consumers
refuse to proceed. Check that the process has ended, then preserve and inspect
the previous/new directories listed in the marker. Multiple file replacements
are not treated as one atomic write.

## References / 참고 자료

- [Oshima et al., GaREUS](https://doi.org/10.1021/acs.jctc.9b00761)
- [GENESIS GaREUS tutorial](https://mdgenesis.org/tutorials/genesis_tutorial_12.5_2022/)
- [PyMBAR documentation](https://pymbar.readthedocs.io/)

This analysis reads the tutorial’s `restraint.production.dat` and `gamd.production.log` in each window. The output TSV retains `segment = 1`. Segmented template outputs are not supported.

Public analysis entries automatically use `writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
