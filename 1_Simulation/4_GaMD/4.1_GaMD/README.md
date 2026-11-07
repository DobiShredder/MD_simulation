# Chignolin Gaussian accelerated MD / Chignolin GaMD

## 한국어

PDB 1UAO의 첫 NMR model을 ff19SB/OPC로 build하고 dual-boost GaMD를
실행합니다. 계산은 minimization, 200 ps heating, 100 ps NPT equilibration,
4 ns GaMD parameter preparation과 1 ns production 순서입니다.

Standard dual-boost GaMD는 total potential과 dihedral potential에 서로 다른
boost를 적용합니다. Dihedral barrier와 전체 potential fluctuation을 함께
완화합니다. Reweighting이 가능한지는 production log에서 두 component와 그 합의
distribution을 보고 판단합니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 첫 NMR model의 138 atoms를 simulation PDB로 정리합니다. |
| `build.sh` | ff19SB/OPC topology와 solvated restart를 만듭니다. |
| `run.sh` | Conventional stage, 4 ns parameter preparation과 production을 실행합니다. |
| `anal.py` | 두 boost component와 total boost의 통계를 TSV로 저장합니다. |

~~~bash
cd 1_Simulation/4_GaMD/4.1_GaMD
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh
python3 anal.py
~~~

필요한 program과 stage별 계산량은 [GaMD README](../README.md#필요한-program)에
정리되어 있습니다.

`work/gamd-restart.dat`에는 preparation에서 결정한 boost parameter가 저장되고,
production은 `irest_gamd=1`로 이 값을 이어받습니다.

### 성공 확인

| Command | 마지막 출력 | 확인할 파일 |
| --- | --- | --- |
| `./build.sh` | `AMBER topology and restart: work` | `work/system.parm7`, `work/system.rst7` |
| `./run.sh` | `1 ns GaMD production completed: work/production.nc` | `work/gamd_prepare.gamd.rst`, `work/production.gamd.log`(header 뒤 100 records) |
| `python3 anal.py` | `GaMD boost diagnostics: work/boost_summary.tsv` | `work/boost_summary.tsv`, `work/boost_frames.tsv` |

결과 column의 해석은 [GaMD README](../README.md#결과-해석)를 참고합니다. 다음
단계는 PMF reweighting입니다.

~~~bash
cd ../../../2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting
./run.sh chignolin ../../../1_Simulation/4_GaMD/4.1_GaMD/work
~~~

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
| `ntr=1`, `-ref minimize.rst7` | Heating 동안 non-solvent atom을 minimization 구조에 restraint합니다. |
| Heating seed `41001` | 이 고정 example의 initial velocity seed입니다. |

기본 engine은 `pmemd.cuda`이며 `AMBER_ENGINE`으로 executable만 바꿀 수 있습니다.
System별 설정과 여러 production run은 `3_Templates/4_GaMD/4.1_GaMD`에서
구성합니다.

### Production 재실행

Production은 시작할 때 `work/.production.started`를 남깁니다. Production이 실패한
뒤 다시 실행하면 남은 output과 engine이 바꾼 `work/gamd-restart.dat`을
preparation state로 덮어쓰지 않고 중단합니다. Error에 나온 파일을 `work` 밖으로
옮긴 뒤 다시 실행합니다. Preparation state는 `work/gamd_prepare.gamd.rst`에
남아 있으므로 production은 이 state에서 다시 시작합니다.

~~~bash
mkdir -p work.failed
mv work/production.* work/.production.started work/gamd-restart.dat work.failed/
./run.sh
~~~

완료된 production은 다시 실행하지 않습니다. Engine을 실행하지 않고
`Skipping completed production`과 다음 command `python3 anal.py`를 출력한 뒤
정상 종료합니다. 그 밖의 실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### 문제 해결

| Message | 원인과 조치 |
| --- | --- |
| `Error: tleap not found: tleap` | AmberTools 26 environment를 activate하거나 `TLEAP`에 executable을 지정합니다. |
| `Error: tleap failed. See work/tleap.stdout.log and work/leap.log` | `leap.log`에서 residue나 atom 이름 error를 찾고 `prepare.py` output을 확인합니다. |
| `Error: Run build.sh first: work` | `work/system.parm7`이나 `work/system.rst7`이 없습니다. `./build.sh`를 먼저 실행합니다. |
| `Error: AMBER engine not found: pmemd.cuda` | Amber 26 `pmemd.cuda`를 `PATH`에 두거나 `AMBER_ENGINE`에 경로를 지정합니다. |
| `... calculation failed. Partial ... output is retained: ...` | `work/engine.STAGE.log`와 `work/STAGE.out` 마지막 부분이 출력됩니다. 원인을 고친 뒤 error에 나온 파일을 옮기고 다시 실행합니다. |
| `work/production.gamd.log: 100 GaMD records is required: N` | Production이 끝나지 않았거나 `ntwx`/`nstlim`을 바꿨습니다. `anal.py`는 100 records만 받습니다. |

1 ns trajectory와 reweighted PMF는 folding equilibrium 또는 수렴 결과가
아닙니다.

## English

The first NMR model of PDB 1UAO is built with ff19SB/OPC. The workflow runs
minimization, 200 ps heating, 100 ps NPT equilibration, 4 ns of GaMD parameter
preparation, and one 1 ns dual-boost production run.

Standard dual-boost GaMD applies separate boosts to the total and dihedral
potentials, easing dihedral barriers and overall potential fluctuations. Inspect
the two boost components and their sum in the production log before
reweighting.

### Script roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads 1UAO PDB/mmCIF and records checksums. |
| `prepare.py` | Writes the 138 atoms of the first NMR model as the simulation PDB. |
| `build.sh` | Creates the ff19SB/OPC topology and solvated restart. |
| `run.sh` | Runs the conventional stages, 4 ns parameter preparation and production. |
| `anal.py` | Writes statistics of both boost components and the total boost to TSV. |

~~~bash
cd 1_Simulation/4_GaMD/4.1_GaMD
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh
python3 anal.py
~~~

Required programs and per-stage computation are listed in the
[GaMD README](../README.md#required-programs).

`work/gamd-restart.dat` stores the boost parameters determined during
preparation, and production continues them with `irest_gamd=1`.

### Success check

| Command | Last line | Files to check |
| --- | --- | --- |
| `./build.sh` | `AMBER topology and restart: work` | `work/system.parm7`, `work/system.rst7` |
| `./run.sh` | `1 ns GaMD production completed: work/production.nc` | `work/gamd_prepare.gamd.rst`, `work/production.gamd.log` (100 records after the header) |
| `python3 anal.py` | `GaMD boost diagnostics: work/boost_summary.tsv` | `work/boost_summary.tsv`, `work/boost_frames.tsv` |

See the [GaMD README](../README.md#interpreting-the-results) for the result
columns. The next step is PMF reweighting.

~~~bash
cd ../../../2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting
./run.sh chignolin ../../../1_Simulation/4_GaMD/4.1_GaMD/work
~~~

### Key options

| Option | Meaning |
| --- | --- |
| `igamd=3` | Selects the total-potential and dihedral dual boost. |
| `iE=1` | Uses the lower-bound energy threshold. |
| `sigma0P=6.0`, `sigma0D=6.0` | Upper limits (kcal/mol) on the target standard deviation of the total/dihedral boosts. |
| `ntcmdprep`, `ntcmd` | Conventional MD steps that prepare the initial potential estimate, and the total initial conventional MD steps that collect energy statistics. |
| `ntebprep`, `nteb` | Steps that prepare boost introduction, and the total boosted GaMD equilibration steps. These are overlapping schedule controls, not four durations to sum. |
| `ntave=50000` | Averaging interval for energy-statistics updates, 100 ps at 2 fs. |
| `irest_gamd=0/1` | Preparation creates the state; production continues from `gamd-restart.dat`. |
| `ntwx=5000`, `-gamd` | Matches trajectory and boost-log records at 10 ps. |
| `ntr=1`, `-ref minimize.rst7` | Restrains non-solvent atoms to the minimized structure during heating. |
| Heating seed `41001` | Initial velocity seed of this fixed example. |

The default engine is `pmemd.cuda`; `AMBER_ENGINE` changes only the executable.
Use `3_Templates/4_GaMD/4.1_GaMD` for system-specific settings or repeated
production runs.

### Rerunning production

Production leaves an attempt record, `work/.production.started`. After a failed
production, a rerun stops instead of overwriting the leftover output or the
engine-modified `work/gamd-restart.dat` with the prepared state. Move the files
named in the error out of `work` and rerun. The prepared state remains in
`work/gamd_prepare.gamd.rst`, so production restarts from it.

~~~bash
mkdir -p work.failed
mv work/production.* work/.production.started work/gamd-restart.dat work.failed/
./run.sh
~~~

A completed production is not rerun: `run.sh` skips the engine, prints
`Skipping completed production` and the next command, `python3 anal.py`, and
exits 0. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for
other run state, reruns after failure and concurrent-run protection.

### Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `Error: tleap not found: tleap` | Activate the AmberTools 26 environment or set `TLEAP` to the executable. |
| `Error: tleap failed. See work/tleap.stdout.log and work/leap.log` | Look for residue or atom-name errors in `leap.log` and check the `prepare.py` output. |
| `Error: Run build.sh first: work` | `work/system.parm7` or `work/system.rst7` is missing. Run `./build.sh` first. |
| `Error: AMBER engine not found: pmemd.cuda` | Put Amber 26 `pmemd.cuda` on `PATH` or set `AMBER_ENGINE` to its path. |
| `... calculation failed. Partial ... output is retained: ...` | The tails of `work/engine.STAGE.log` and `work/STAGE.out` are printed. Fix the cause, move the listed files and rerun. |
| `work/production.gamd.log: 100 GaMD records is required: N` | Production did not finish, or `ntwx`/`nstlim` was changed. `anal.py` accepts exactly 100 records. |

The 1 ns trajectory and reweighted PMF do not establish folding equilibrium or
convergence.

## References / 참고 자료

- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)
- [GaMD AMBER manual](https://www.med.unc.edu/pharm/miaolab/wp-content/uploads/sites/1385/2023/09/GaMD_Amber-manual.pdf)
