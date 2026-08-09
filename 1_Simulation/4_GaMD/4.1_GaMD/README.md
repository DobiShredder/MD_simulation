# Chignolin Gaussian accelerated MD / Chignolin GaMD

## 한국어

PDB 1UAO의 첫 NMR model을 ff19SB/TIP3P로 build하고 dual-boost GaMD를
실행합니다. 계산은 minimization, 200 ps heating, 1 ns NPT equilibration,
4 ns GaMD parameter preparation과 1 ns production segment 10개 순서입니다.

Standard dual-boost GaMD는 total potential과 dihedral potential에 서로 다른
boost를 적용합니다. Dihedral barrier와 전체 potential fluctuation을 함께
완화하지만, 두 component의 합과 distribution을 production log에서 확인해야
reweighting 가능성을 판단할 수 있습니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 첫 NMR model의 138 atoms를 simulation PDB로 정리합니다. |
| `build.sh` | ff19SB/TIP3P topology와 solvated restart를 만듭니다. |
| `run.sh` | Conventional stage, 4 ns parameter preparation과 10개 production segment를 실행합니다. |
| `anal.py` | 두 boost component와 total boost의 segment별 통계를 TSV로 저장합니다. |

~~~bash
cd 1_Simulation/4_GaMD/4.1_GaMD
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
~~~

`igamd=3`은 total potential과 dihedral potential에 boost를 적용합니다.
`work/gamd-restart.dat`에는 preparation에서 결정한 boost parameter가 저장되고,
production은 `irest_gamd=1`로 이 값을 이어받습니다. 완료된 stage의 GaMD state는
`*.gamd.rst` snapshot으로 보존합니다. Segment 하나의 output만 일부 존재하면
`run.sh`는 중단합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `igamd=3` | Total-potential과 dihedral dual boost를 선택합니다. |
| `iE=1` | Lower-bound energy threshold 형식을 사용합니다. |
| `sigma0P=6.0`, `sigma0D=6.0` | Total/dihedral boost의 target standard deviation 상한(kcal/mol)입니다. |
| `ntcmdprep`, `ntcmd` | Initial potential estimate를 준비하는 conventional MD steps와 energy statistics를 수집하는 전체 initial conventional MD steps입니다. |
| `ntebprep`, `nteb` | Boost 도입 준비 steps와 boost를 적용한 GaMD equilibration steps입니다. 네 값을 독립 구간처럼 더하지 않습니다. |
| `ntave=50000` | Energy statistics update에 사용하는 averaging interval입니다. 2 fs 기준 100 ps입니다. |
| `irest_gamd=0/1` | Preparation에서 state를 만들고 production에서 `gamd-restart.dat`을 이어받습니다. |
| `ntwx=5000`, `-gamd` | Trajectory와 boost log를 10 ps 간격으로 맞춥니다. |

기본 engine은 `pmemd.cuda`입니다. 다른 executable은 `AMBER_ENGINE`, 별도
output directory는 `WORK_DIR`, heating seed는 `RANDOM_SEED`로 지정합니다.
10 ns trajectory와 reweighted PMF는 folding equilibrium 또는 수렴 결과가
아닙니다.

## English

The first NMR model of PDB 1UAO is built with ff19SB/TIP3P. The workflow runs
minimization, 200 ps heating, 1 ns NPT equilibration, 4 ns of GaMD parameter
preparation, and ten 1 ns dual-boost production segments.

Standard dual-boost GaMD accelerates both total and dihedral potentials. The
two boost components and their sum must be inspected before reweighting.
`download.sh`/`prepare.py` select 1UAO, `build.sh` creates the ff19SB/TIP3P
system, `run.sh` performs preparation and segmented production, and `anal.py`
writes component-wise diagnostics.

`igamd=3`, `iE=1` select lower-bound dual boost. `sigma0P`/`sigma0D` limit the
target boost standard deviations. `ntcmdprep` prepares the initial estimate and
`ntcmd` defines the initial conventional-statistics phase; `ntebprep` prepares
boost introduction and `nteb` defines GaMD equilibration. These are overlapping
schedule controls, not four durations to sum. `ntave=50000` gives a 100 ps
averaging interval. Production uses `irest_gamd=1`; `ntwx=5000` and
`-gamd` provide matched 10 ps records.

Production continues with `irest_gamd=1`; each completed stage preserves a
`*.gamd.rst` state snapshot beside its MD restart. Set `AMBER_ENGINE`,
`WORK_DIR`, or `RANDOM_SEED` for another executable, independent run directory,
or positive heating seed. The 10 ns example does not establish folding
equilibrium or convergence.

## References / 참고 자료

- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)
- [GaMD AMBER manual](https://www.med.unc.edu/pharm/miaolab/wp-content/uploads/sites/1385/2023/09/GaMD_Amber-manual.pdf)
