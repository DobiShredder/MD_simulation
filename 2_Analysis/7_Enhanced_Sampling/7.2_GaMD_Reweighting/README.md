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
GaMD log는 각각 1,000 frames여야 합니다.

`pmf.tsv`에는 biased/reweighted probability와 PMF, bin별 boost 평균·분산과
effective sample size가 기록됩니다. 기본 bin width는 0.25 Å입니다. CV 범위는
관측 범위에서 계산하며 비어 있는 bin은 쓰지 않습니다.

10 ns example의 noisy PMF를 정량 free energy로 사용하지 않습니다. 서로 다른
independent run, bin sensitivity, anharmonicity, effective sample size와 sampling
convergence를 함께 확인합니다. Kinetic reweighting과 2D PMF는 포함하지 않습니다.

필요한 program은 cpptraj, Python 3와 NumPy입니다.

## English

cpptraj calculates one profile-specific CV from the ten production segments.
The Python script joins 1,000 CV and boost records and applies second-order
cumulant expansion to produce a one-dimensional PMF.

`pmf.tsv` reports biased and reweighted probabilities and PMFs, per-bin boost
mean and variance, and effective sample size. The 10 ns result is a workflow
example, not a converged free energy. Kinetic reweighting and two-dimensional
PMFs are outside this example.

## References / 참고 자료

- [GaMD AMBER manual](https://www.med.unc.edu/pharm/miaolab/wp-content/uploads/sites/1385/2023/09/GaMD_Amber-manual.pdf)
- [PyReweighting](https://github.com/MiaoLab20/pyreweighting)
