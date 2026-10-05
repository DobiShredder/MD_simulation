# GaMD reweighting / GaMD reweighting 분석

## 한국어

GaMD production trajectory에서 cpptraj으로 1D CV를 계산하고, GaMD boost
potential을 2차 cumulant expansion으로 reweight합니다.

~~~bash
cd 2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting
./run.sh chignolin ../../../1_Simulation/4_GaMD/4.1_GaMD/work
./run.sh ligamd3 ../../../1_Simulation/4_GaMD/4.2_LiGaMD3/work
./run.sh pepgamd ../../../1_Simulation/4_GaMD/4.3_Pep-GaMD/work
~~~

Profile별 CV는 Chignolin terminal Cα distance, BEN–Asp189 side-chain COM
distance와 receptor alignment 후 peptide backbone RMSD입니다. `cv.dat`과
GaMD log는 각각 100 frames여야 합니다.

### Script 역할

| Script | 실행 방식 | 역할 |
| --- | --- | --- |
| `run.sh` | 직접 실행 | CV 계산과 reweighting을 순서대로 실행하고 결과를 게시합니다. |
| `prepare.py` | 자동 호출 | Profile별 topology, trajectory와 metadata로 cpptraj input을 만듭니다. |
| `reweight.py` | 자동 호출 또는 parameter 조정 시 직접 실행 | CV/boost frame 수를 확인하고 2차 cumulant expansion으로 PMF를 계산합니다. |
| `result_generation.py` | 자동 호출 | 결과 묶음을 검증·게시하고 완료 hash를 기록합니다. |

일반적인 사용에서는 `run.sh`만 실행하면 됩니다. 중간 결과를 확인하거나
분석 parameter를 수정할 때만 Python script를 직접 실행합니다.

`pmf.tsv`에는 biased/reweighted probability와 PMF, bin별 boost 평균·분산과
effective sample size가 기록됩니다. 기본 bin width는 0.25 Å입니다. CV 범위는
관측 범위에서 계산하며 비어 있는 bin은 쓰지 않습니다.

LiGaMD3도 Amber 26 `gamd.log`에 기록된 `Boost-Energy-Potential`과
`Boost-Energy-Dihedral` 두 aggregate column을 읽습니다. 두 값의 합을
reweighting에 필요한 frame별 total boost `ΔV`로 사용합니다.

1 ns example의 noisy PMF를 정량 free energy로 사용하지 않습니다. 서로 다른
independent run, bin sensitivity, anharmonicity, effective sample size와 sampling
convergence를 함께 확인합니다. Kinetic reweighting과 2D PMF는 포함하지 않습니다.

필요한 program은 cpptraj, Python 3와 NumPy입니다.

### 결과 저장과 재실행

`run.sh`는 profile별 temporary directory에서 cpptraj input, CV와 PMF를
생성합니다. 새 CV와 reweighting 결과가 모두 확인된 뒤 최종 directory를
교체합니다. 어느 단계에서 실패해도 이전 결과와 log를 유지하며, 실패한
cpptraj log의 마지막 부분은 stderr에 출력합니다.

`result_generation.py`는 자동 호출되는 내부 helper입니다. 완료한 파일의 hash를
결과 directory의 `.generation.json`에 기록합니다. 기본 경로는 `output/PROFILE`이며
`OUTPUT_DIR`로 바꿀 수 있습니다. 게시가 중단되면 같은 parent의
`.PROFILE.pending`에 적힌 previous/new directory를 보존하고 검사합니다.
Marker가 남아 있는 동안 재실행은 거부합니다.

공개 analysis entry는 자동으로 `writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

cpptraj calculates one profile-specific CV from the production run.
`prepare.py` creates the profile-specific cpptraj input. `reweight.py` checks
the one-to-one correspondence between 100 CV and boost records and applies
second-order cumulant expansion to produce a one-dimensional PMF. `run.sh` executes these steps in order.

`pmf.tsv` reports biased and reweighted probabilities and PMFs, per-bin boost
mean and variance, and effective sample size. The 1 ns result is a workflow
example, not a converged free energy. Kinetic reweighting and two-dimensional
PMFs are outside this example.

For LiGaMD3, the parser reads Amber 26's two logged aggregate columns,
`Boost-Energy-Potential` and `Boost-Energy-Dihedral`, and uses their sum as the
per-frame total boost `ΔV` for reweighting.

### Result storage and reruns

`run.sh` creates the cpptraj input, CV, and PMF in a profile-specific temporary
directory. It replaces the final directory only after checking the new CV and
reweighting outputs. Failure at either stage preserves previous results and
logs; recent failed cpptraj log lines are printed to stderr.

`result_generation.py` is called automatically and records completed file hashes
in `.generation.json`. The default result directory is `output/PROFILE`, with
`OUTPUT_DIR` available as an override. An interrupted publication leaves
`.PROFILE.pending` in the same parent directory. Preserve and inspect the
previous/new directories listed there; reruns refuse while the marker remains.

## References / 참고 자료

- [GaMD AMBER manual](https://www.med.unc.edu/pharm/miaolab/wp-content/uploads/sites/1385/2023/09/GaMD_Amber-manual.pdf)
- [PyReweighting](https://github.com/MiaoLab20/pyreweighting)

Public analysis entries automatically use `writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
