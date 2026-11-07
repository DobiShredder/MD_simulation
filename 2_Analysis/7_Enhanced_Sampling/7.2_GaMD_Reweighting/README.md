# GaMD reweighting / GaMD reweighting 분석

## 한국어

GaMD production trajectory에서 cpptraj으로 1D CV를 계산하고, GaMD boost
potential을 2차 cumulant expansion으로 reweight합니다.

[`4_GaMD`](../../../1_Simulation/4_GaMD/README.md)의 각 tutorial production을
먼저 완료합니다. `run.sh`는 profile 이름과 해당 simulation의 `work` directory를
받습니다. 필요한 program은 cpptraj, Python 3와 NumPy입니다.

~~~bash
cd 2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting
./run.sh chignolin ../../../1_Simulation/4_GaMD/4.1_GaMD/work
./run.sh ligamd3 ../../../1_Simulation/4_GaMD/4.2_LiGaMD3/work
./run.sh pepgamd ../../../1_Simulation/4_GaMD/4.3_Pep-GaMD/work
~~~

Profile별 CV는 Chignolin terminal Cα distance, BEN heavy-atom COM–Asp189 carboxylate(OD1, OD2) COM
distance와 receptor alignment 후 peptide backbone RMSD입니다. `cv.dat` frame
수와 GaMD log의 boost record 수가 같아야 합니다. 기본 1 ns example은 둘 다
100입니다.

### Script 역할

| Script | 실행 방식 | 역할 |
| --- | --- | --- |
| `run.sh` | 직접 실행 | CV 계산과 reweighting을 순서대로 실행하고 결과를 게시합니다. |
| `prepare.py` | 자동 호출 | Profile별 topology, trajectory와 metadata로 cpptraj input을 만듭니다. |
| `reweight.py` | 자동 호출 또는 parameter 조정 시 직접 실행 | CV/boost frame 수를 확인하고 2차 cumulant expansion으로 PMF를 계산합니다. |
| `result_generation.py` | 자동 호출 | 결과 묶음을 검증·게시하고 완료 hash를 기록합니다. |

일반적인 사용에서는 `run.sh`만 실행하면 됩니다. 중간 결과를 확인하거나
분석 parameter를 수정할 때만 Python script를 직접 실행합니다.

결과는 `output/PROFILE/`에 생성됩니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `cpptraj.in`, `cpptraj.log` | `prepare.py`가 만든 CV input과 cpptraj log | — |
| `cv.dat` | `#Frame`과 profile별 CV 값 | Å |
| `pmf.tsv` | `bin_center`, `count`, `biased_probability`, `reweighted_probability`, `biased_pmf_kcal_mol`, `reweighted_pmf_kcal_mol`, `boost_mean_kcal_mol`, `boost_variance_kcal2_mol2`, `effective_sample_size` | Å, kcal/mol, kcal²/mol² |

두 PMF는 각각 최솟값이 0입니다. `effective_sample_size`가 작은 bin의
reweighted PMF는 소수 frame의 큰 boost에 좌우됩니다.

Reweighting parameter는 `run.sh` 상단에 있습니다. `temperature_kelvin`(300 K)은
GaMD production input의 `temp0`와 같아야 하고, `bin_width_angstrom`(0.25 Å)은
CV bin 폭입니다. CV 범위는 관측 범위에서 계산하며 비어 있는 bin은 쓰지
않습니다. `reweight.py`는 읽은 frame 수를 `Frames: N`으로 출력합니다.

LiGaMD3도 Amber 26 `gamd.log`에 기록된 `Boost-Energy-Potential`과
`Boost-Energy-Dihedral` 두 aggregate column을 읽습니다. 두 값의 합을
reweighting에 필요한 frame별 total boost `ΔV`로 사용합니다.

1 ns example의 noisy PMF를 정량 free energy로 사용하지 않습니다. 서로 다른
independent run, bin sensitivity, anharmonicity, effective sample size와 sampling
convergence를 함께 확인합니다. Kinetic reweighting과 2D PMF는 포함하지 않습니다.

이 directory는 profile별로 게시합니다. 결과 directory는 `output/PROFILE`
(`OUTPUT_DIR`로 변경 가능), 실패 log는 `output/PROFILE.failed/`, 중단 marker는
같은 parent의 `.PROFILE.pending`입니다. 나머지 게시 규칙과 동시 실행
보호(`writer_guard.py`)는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

cpptraj calculates one profile-specific CV from the GaMD production run, and
the GaMD boost is reweighted with a second-order cumulant expansion.

Complete the production of each
[`4_GaMD`](../../../1_Simulation/4_GaMD/README.md) tutorial first. `run.sh`
takes the profile name (`chignolin`, `ligamd3` or `pepgamd`) and that
simulation's `work` directory, for example
`./run.sh chignolin ../../../1_Simulation/4_GaMD/4.1_GaMD/work`. It requires
cpptraj, Python 3, and NumPy.

The profile CVs are the Chignolin terminal Cα distance, the BEN heavy-atom
COM to Asp189 carboxylate (OD1, OD2) COM distance, and the peptide backbone RMSD after receptor
alignment. The `cv.dat` frame count must match the GaMD boost record count
(100 each in the default 1 ns example).

`prepare.py` creates the profile-specific cpptraj input. `reweight.py` checks
the record counts and applies the second-order cumulant expansion to produce a
one-dimensional PMF. `run.sh` executes these steps in order, and the
automatically called `result_generation.py` publishes the result. Run the
Python scripts directly only to inspect intermediate results or change analysis
parameters.

Results are written to `output/PROFILE/`.

| Output | Columns | Unit |
| --- | --- | --- |
| `cpptraj.in`, `cpptraj.log` | CV input written by `prepare.py` and the cpptraj log | — |
| `cv.dat` | `#Frame` and the profile CV | Å |
| `pmf.tsv` | `bin_center`, `count`, `biased_probability`, `reweighted_probability`, `biased_pmf_kcal_mol`, `reweighted_pmf_kcal_mol`, `boost_mean_kcal_mol`, `boost_variance_kcal2_mol2`, `effective_sample_size` | Å, kcal/mol, kcal²/mol² |

Each PMF is shifted to a zero minimum. In bins with a small
`effective_sample_size`, a few frames with large boosts dominate the
reweighted PMF.

The reweighting parameters are at the top of `run.sh`: `temperature_kelvin`
(300 K) must match `temp0` in the GaMD production input, and
`bin_width_angstrom` (0.25 Å) sets the CV bin width. The CV range follows the
observed values, and empty bins are not written. `reweight.py` prints the
number of frames read as `Frames: N`.

For LiGaMD3, the parser reads Amber 26's two logged aggregate columns,
`Boost-Energy-Potential` and `Boost-Energy-Dihedral`, and uses their sum as the
per-frame total boost `ΔV` for reweighting.

The 1 ns result is a workflow example, not a converged free energy. Check
independent runs, bin sensitivity, anharmonicity, effective sample size, and
sampling convergence together. Kinetic reweighting and two-dimensional PMFs are
outside this example.

Publication here is per profile: results go to `output/PROFILE` (override with
`OUTPUT_DIR`), failure logs to `output/PROFILE.failed/`, and an interrupted
publication leaves `.PROFILE.pending` in the same parent. The remaining
publication rules and concurrent-run protection (`writer_guard.py`) are
described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).

## References / 참고 자료

- [GaMD AMBER manual](https://www.med.unc.edu/pharm/miaolab/wp-content/uploads/sites/1385/2023/09/GaMD_Amber-manual.pdf)
- [PyReweighting](https://github.com/MiaoLab20/pyreweighting)
