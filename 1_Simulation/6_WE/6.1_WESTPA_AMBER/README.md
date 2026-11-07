# Chignolin WESTPA–AMBER weighted ensemble

Reference syntax: Amber 2026 and WESTPA 2.

## 한국어

PDB 1UAO Chignolin을 explicit OPC water에서 전파하고 residue 2–9의 Cα RMSD를
progress coordinate로 사용합니다. Conventional MD와 같은 unbiased AMBER
dynamics를 실행하지만, WESTPA가 1 ps마다 walker를 RMSD bin에 배치하고
split/merge하여 bin당 walker 수를 조정합니다. Split된 walker의 weight 합과
parent restart는 보존되며 각 child는 서로 다른 Langevin seed로 이어집니다.

RMSD 3.0 Å 이상은 resampling과 target 분석을 연습하기 위한 partially unfolded
state입니다. 20 iterations의 짧은 기본 run에서는 target event가 없을 수 있으며,
event 수나 target weight를 folding/unfolding rate로 해석하지 않습니다.

준비할 software(WESTPA 2, AMBER, `h5py`)는 [상위 README](../README.md)에 있습니다.

### Script 역할

| 파일 | 실행 방식 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 직접 실행 | PDB 1UAO → `structure/1UAO.raw.pdb`, checksum |
| `prepare.py` | 직접 실행 | NMR model 1 → `structure/chignolin.pdb` |
| `build.sh` | 직접 실행 | Chignolin PDB → ff19SB/OPC topology, RMSD reference와 basis restart |
| `env.sh` | 자동 호출 | WESTPA root, work directory, AMBER/cpptraj executable 설정 |
| `init.sh` | 직접 실행 | Basis/target state → `work/west.h5` |
| `run.sh` | 직접 실행 | WESTPA iterations → segment restart, log와 갱신된 `west.h5` |
| `westpa_scripts/runseg.sh` | WESTPA가 호출 | Parent restart → 1 ps AMBER segment(`seg.rst7`, `seg.nc`)와 두 pcoord 값 |
| `anal.py` | 직접 실행 | Weight, effective walker, RMSD 범위, bin occupancy와 target 진단 TSV |

### 실행

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./init.sh
./run.sh
python3 anal.py
```

### 계산량

| 단계 | 길이 | 실행 횟수 |
| --- | --- | --- |
| Basis state 준비(`build.sh`) | Minimization 5000 cycles, heating 50,000 steps(100 ps), NPT equilibration 50,000 steps(100 ps) | 1회 |
| WE segment(`run.sh`) | 500 steps(τ = 1 ps) | 첫 iteration 4개, 이후 occupied bin 수 × 4개(최대 40개: bin 11개 중 target bin `[3.0, inf)`은 recycle되어 전파하지 않음) |
| 전체 WE run | 20 iterations | 최대 764 segments(4 + 19 × 40), MD 합계 최대 764 ps |

Segment는 serial work manager로 한 GPU에서 하나씩 실행합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/iteration_summary.tsv` | Iteration별 total weight, effective walker 수와 RMSD 범위. Total weight는 1에 가까워야 합니다. |
| `work/bin_occupancy.tsv` | Iteration별 bin의 segment 수와 weight |
| `work/target_events.tsv` | RMSD 3.0 Å 이상에 도달한 segment |

`anal.py`는 total weight를 1로 강제 보정하지 않고 실제 합을 출력합니다. Weight가
음수이거나 finite가 아니면, 또는 완료 iteration에 미완료 segment가 있으면 기존
TSV를 바꾸기 전에 중단합니다. Current iteration보다 작은 iteration만 읽으므로 다음
propagation을 위해 미리 만든 pending group은 포함하지 않습니다.

### 결과 확인

`run.sh`가 끝까지 실행되면 다음 줄을 출력합니다. `paused`가 출력되면
`./run.sh`를 다시 실행합니다.

```text
WESTPA run completed: 20 iterations; state: .../work/west.h5; log: .../work/west.log
```

`python3 anal.py` 뒤에는 `iteration_summary.tsv`의 `total_weight`가 모든
iteration에서 1에 가까운지, `segments`가 occupied bin 수 × 4인지 봅니다.
`bin_occupancy.tsv`에서는 높은 RMSD bin에 weight가 생기는 iteration을 확인합니다.

### 결과 해석

`target_events.tsv`의 `target_weight`는 그 iteration에 target bin으로 들어간
probability, 즉 τ(1 ps)당 flux입니다. Steady state에 도달한 긴 run에서는 평균
flux를 τ로 나눈 값이 Hill relation에 따른 rate 추정값입니다(Zuckerman & Chong,
*Annu. Rev. Biophys.* 46:43, 2017). 20 iterations로는 steady state를 판단할 수
없습니다. WESTPA `w_assign`, `w_direct`로 flux를 계산하는 절차는
[template README](../../../3_Templates/6_WE/6.1_WESTPA_AMBER/README.md)에 있습니다.

### 주요 option

| Option | 값 | 위치 | 의미 |
| --- | --- | --- | --- |
| `solvatebox ... OPCBOX` | 12.0 Å | `inputs/leap.in` | Solute와 box edge 사이 water 두께 |
| `maxcyc`, `ncyc` | 5000, 2500 | `inputs/minimize.in` | 전체 minimization cycle과 그중 steepest-descent cycle |
| `tempi` → `temp0` | 20 → 300 K | `inputs/heat.in` | 50,000 steps 동안 NVT heating |
| `restraint_wt` | 5.0 kcal mol⁻¹ Å⁻² | `inputs/heat.in` | Heating 중 solute heavy atom restraint |
| `pres0`, `barostat` | 1.0 bar, 2 | `inputs/equilibrate.in`, segment | Monte Carlo barostat를 쓰는 NPT |
| `nstlim`, `dt` | 500, 0.002 ps | `inputs/segment.in.template` | Segment 길이 τ = 1 ps |
| `temp0`, `gamma_ln` | 300 K, 1.0 ps⁻¹ | 모든 MD input | Langevin thermostat |
| `cut` | 10.0 Å | 모든 AMBER input | Direct-space nonbonded cutoff |
| `bin_target_counts` | 4 | `west.cfg` | Occupied bin당 walker 수 |
| `boundaries` | 0, 0.5, 0.75, …, 2.5, 3.0, inf Å | `west.cfg` | RMSD bin 경계 |
| `max_total_iterations` | 20 | `west.cfg` | 총 iteration 수 |
| `max_run_wallclock` | 02:00:00 | `west.cfg` | `w_run` 한 번의 최대 실행 시간 |
| `--segs-per-state` | 4 | `init.sh` | Basis state에서 시작하는 walker 수 |
| Target 값 | 3.25 Å | `tstate.file` | Target bin 안의 representative value |

`build.sh`는 위 준비 단계를 거쳐 `work/bstates/basis.rst7`을 생성합니다.
`west.h5`나 segment output이 있으면 기존 WESTPA state를 보호하기 위해 build를
중단합니다.

Heating과 equilibration은 `ntwx=5000`으로 `heat.nc`와 `equilibrate.nc`에 10 ps마다
frame을 저장합니다. Segment는 500 steps(1 ps)라 5000 steps 간격으로는 frame이
남지 않으므로 `ntwx=500`으로 segment 끝 frame 하나를 `seg.nc`에 저장합니다.
Progress coordinate는 trajectory가 아니라 `seg.rst7`에서 계산합니다.

Minimized structure인 `work/common_files/reference.rst7`에 residue 2–9 Cα를
least-squares fit한 RMSD를 Å 단위로 계산합니다. Terminal residue를 제외하면
말단 움직임이 progress coordinate를 지배하는 현상을 줄일 수 있습니다.

RMSD bin은 0–3 Å 구간에서 조밀하게 나뉘고 `[3.0, inf)`가 target bin입니다. Cα RMSD는
서로 다른 unfolded conformation을 같은 값으로 투영할 수 있으므로, 연구용
계산에서는 native contact나 다른 coordinate를 추가하고 binning을 다시
설계합니다.

Target bin에 도달한 walker의 weight는 다음 iteration에서 folded basis state로
recycling됩니다. 따라서 생성된 walker 집합은 equilibrium conformational
ensemble이 아닙니다. 이 tutorial에서는 recycling과 weight 전달을 관찰하는
용도로만 사용합니다.

Segment input의 `irest=1`, `ntx=5`는 parent coordinate와 velocity를 이어받습니다.
`WEST_RAND32`에서 positive Langevin seed를 만들어 split된 walker가 같은
random-number stream을 반복하지 않게 합니다.

기본 engine은 한 GPU에서 serial work manager로 실행하는 `pmemd.cuda`입니다.
Executable만 `AMBER_ENGINE`으로 바꿀 수 있습니다. CPU worker 수와 system별
WESTPA 설정은 `3_Templates/6_WE/6.1_WESTPA_AMBER`에서 구성합니다.

### 이어서 실행과 reset

기존 `work/west.h5`를 이어서 실행할 때는 `./run.sh`를 다시 실행합니다. `run.sh`는
`west.cfg`의 requested iteration 수와 HDF5의 `west_current_iteration-1`을
비교합니다. `max_run_wallclock`(02:00:00)으로 정상 중단되면 `paused`와 완료한
iteration 수를 출력합니다.

새 run을 시작할 때만 `./init.sh --reset`을 사용합니다. Reset은 `west.h5`,
`west.log`, `traj_segs/`, `seg_logs/`, `istates/`와 `anal.py`가 만든
`work/*.tsv`를 삭제합니다. Reset 전에도 input 검사를 수행하며 input이 바뀌었으면
거부합니다. 변경된 계산은 새 tutorial copy에서 시작합니다.

Kill, node 장애나 scheduler time limit로 iteration 도중 `w_run`이 끊기면 `west.h5`에
미완료 segment가 남습니다. 같은 input으로 `./run.sh`를 다시 실행하면 WESTPA가 그
iteration의 미완료 segment만 다시 전파합니다. WESTPA 2022.15 executable propagator는
`runseg.sh`를 호출하기 전에 미완료 segment의
`work/traj_segs/<iteration>/<segment>/`를 삭제하고 다시 만듭니다. 중단된 segment의
partial AMBER output이 진단에 필요하면 재실행 전에 다른 위치로 복사합니다.

`runseg.sh`가 `Segment output from an earlier propagation attempt was kept`로 멈추면
segment directory에 이전 시도의 output이 있습니다. Callback을 `w_run` 밖에서
실행했거나 partial segment를 지우지 않는 WESTPA version을 쓰면 발생합니다. 내용을
확인한 뒤 error에 출력된 `mv` command로 directory를 `<segment>.failed.<timestamp>`로
옮기고 `./run.sh`를 다시 실행합니다. 실제 AMBER/WESTPA run을 중단한 뒤 재개하는
과정은 검증하지 않았습니다.

### 문제 해결

| Error message | 확인할 것 |
| --- | --- |
| `w_init not found. Activate the WESTPA 2 environment.` | WESTPA를 설치한 environment를 activate합니다. |
| `Run build.sh first: .../bstates/basis.rst7` | `build.sh`가 basis state equilibration까지 끝났는지 봅니다. |
| `An existing WESTPA state was found` | 이어서 실행은 `./run.sh`, 새 run은 `./init.sh --reset`입니다. |
| `AMBER propagation failed with exit status N` | `work/seg_logs/<iteration>-<segment>.log`와 segment directory의 `segment.out` |
| `start progress coordinate failed`, `end progress coordinate failed` | Segment directory의 `pcoord.start.cpptraj.log`, `pcoord.end.cpptraj.log`. Initial state는 `work/get_pcoord.log` |
| `WESTPA run failed`, `A run error was recorded in the WESTPA log` | `run.sh`가 출력한 `work/west.log`와 최근 segment log의 마지막 20줄 |

실행 상태, 실패 후 재실행, 동시 실행 보호와 log 위치는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

## English

This example propagates PDB 1UAO Chignolin in explicit OPC water and uses the
Cα RMSD of residues 2–9 as its progress coordinate. AMBER supplies the same
unbiased dynamics used in conventional MD. Every 1 ps, WESTPA bins the walkers
by RMSD and splits or merges them to adjust the walker count per bin. Splitting
conserves the total weight and the parent restart, and each child continues
with a different Langevin seed.

RMSD of 3.0 Å or more is a partially unfolded state for practicing resampling
and target analysis, not a folding definition. The short default run of 20
iterations may produce no target event, and target counts or weights are not a
folding/unfolding rate estimate.

Required software (WESTPA 2, AMBER, `h5py`) is listed in the
[parent README](../README.md).

### Script roles

| File | How it runs | Main inputs and outputs |
| --- | --- | --- |
| `download.sh` | Run directly | PDB 1UAO → `structure/1UAO.raw.pdb`, checksum |
| `prepare.py` | Run directly | NMR model 1 → `structure/chignolin.pdb` |
| `build.sh` | Run directly | Chignolin PDB → ff19SB/OPC topology, RMSD reference and basis restart |
| `env.sh` | Called automatically | WESTPA root, work directory, AMBER/cpptraj executables |
| `init.sh` | Run directly | Basis/target states → `work/west.h5` |
| `run.sh` | Run directly | WESTPA iterations → segment restarts, logs and updated `west.h5` |
| `westpa_scripts/runseg.sh` | Called by WESTPA | Parent restart → 1 ps AMBER segment (`seg.rst7`, `seg.nc`) and two pcoord values |
| `anal.py` | Run directly | TSV diagnostics of weight, effective walkers, RMSD range, bin occupancy and targets |

### Run

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./init.sh
./run.sh
python3 anal.py
```

### Expected computation

| Stage | Length | Runs |
| --- | --- | --- |
| Basis-state preparation (`build.sh`) | 5000 minimization cycles, 50,000-step heating (100 ps), 50,000-step NPT equilibration (100 ps) | Once |
| WE segment (`run.sh`) | 500 steps (τ = 1 ps) | 4 in the first iteration, then occupied bins × 4 (at most 40: of the 11 bins, the target bin `[3.0, inf)` is recycled and never propagated) |
| Whole WE run | 20 iterations | At most 764 segments (4 + 19 × 40), at most 764 ps of MD in total |

Segments run one at a time on one GPU through the serial work manager.

### Main outputs

| File | Content |
| --- | --- |
| `work/iteration_summary.tsv` | Total weight, effective walker count and RMSD range per iteration. Total weight should stay close to 1. |
| `work/bin_occupancy.tsv` | Segment count and weight per bin and iteration |
| `work/target_events.tsv` | Segments reaching RMSD of 3.0 Å or more |

`anal.py` reports the actual weight sum without renormalizing it to one. Negative
or nonfinite weights, or incomplete segments in a completed iteration, stop the
analysis before existing TSV files are replaced. Only iterations below the
current iteration are read, so pending groups prepared for the next propagation
are excluded.

### Success check

A complete `run.sh` prints the line below. If it prints `paused`, run
`./run.sh` again.

```text
WESTPA run completed: 20 iterations; state: .../work/west.h5; log: .../work/west.log
```

After `python3 anal.py`, check that `total_weight` in `iteration_summary.tsv`
stays close to 1 and that `segments` equals occupied bins × 4. In
`bin_occupancy.tsv`, look for the iterations in which high-RMSD bins gain
weight.

### Interpretation

`target_weight` in `target_events.tsv` is the probability that entered the
target bin in that iteration, i.e. the flux per τ (1 ps). In a long run that has
reached steady state, the mean flux divided by τ estimates the rate through the
Hill relation (Zuckerman & Chong, *Annu. Rev. Biophys.* 46:43, 2017). Twenty
iterations are too few to judge steady state. The
[template README](../../../3_Templates/6_WE/6.1_WESTPA_AMBER/README.md) shows
how to compute fluxes with WESTPA `w_assign` and `w_direct`.

### Key options

| Option | Value | Location | Meaning |
| --- | --- | --- | --- |
| `solvatebox ... OPCBOX` | 12.0 Å | `inputs/leap.in` | Water thickness between solute and box edge |
| `maxcyc`, `ncyc` | 5000, 2500 | `inputs/minimize.in` | Total minimization cycles and steepest-descent cycles |
| `tempi` → `temp0` | 20 → 300 K | `inputs/heat.in` | NVT heating over 50,000 steps |
| `restraint_wt` | 5.0 kcal mol⁻¹ Å⁻² | `inputs/heat.in` | Solute heavy-atom restraint during heating |
| `pres0`, `barostat` | 1.0 bar, 2 | `inputs/equilibrate.in`, segment | NPT with the Monte Carlo barostat |
| `nstlim`, `dt` | 500, 0.002 ps | `inputs/segment.in.template` | Segment length τ = 1 ps |
| `temp0`, `gamma_ln` | 300 K, 1.0 ps⁻¹ | All MD inputs | Langevin thermostat |
| `cut` | 10.0 Å | All AMBER inputs | Direct-space nonbonded cutoff |
| `bin_target_counts` | 4 | `west.cfg` | Walkers per occupied bin |
| `boundaries` | 0, 0.5, 0.75, …, 2.5, 3.0, inf Å | `west.cfg` | RMSD bin edges |
| `max_total_iterations` | 20 | `west.cfg` | Total iterations |
| `max_run_wallclock` | 02:00:00 | `west.cfg` | Maximum duration of one `w_run` call |
| `--segs-per-state` | 4 | `init.sh` | Walkers started from the basis state |
| Target value | 3.25 Å | `tstate.file` | Representative value inside the target bin |

`build.sh` runs the preparation stages above to produce
`work/bstates/basis.rst7`. Existing `west.h5`
or segment output stops the build to protect the initialized WESTPA state.

Heating and equilibration save a frame every 10 ps (`ntwx=5000`) to `heat.nc` and
`equilibrate.nc`. A 500-step (1 ps) segment would write no frame at that
interval, so segments use `ntwx=500` and save their final frame to `seg.nc`.
Progress coordinates are read from `seg.rst7`, not from the trajectory.

RMSD is computed in Å after a least-squares fit of the residue 2–9 Cα atoms to
the minimized structure `work/common_files/reference.rst7`. Excluding the
terminal residues keeps end fraying from dominating the progress coordinate.

Bins are dense between 0 and 3 Å, and `[3.0, inf)` is the target bin. Cα RMSD can map distinct unfolded
conformations to the same value, so research calculations add native contacts
or other coordinates and redesign the bins.

Walkers reaching the target transfer their weight to the folded basis state for
recycling in the next iteration. The resulting walkers therefore do not form an
equilibrium conformational ensemble. Here recycling serves only to observe
weight transfer.

Segments continue parent coordinates and velocities with `irest=1` and
`ntx=5`. A positive Langevin seed derived from `WEST_RAND32` gives split walkers
independent random streams.

The default engine is serial `pmemd.cuda` on one GPU, with only the executable
exposed through `AMBER_ENGINE`. Configure CPU workers and system-specific WESTPA
options in `3_Templates/6_WE/6.1_WESTPA_AMBER`.

### Continuing and resetting

Re-run `./run.sh` to continue an existing `work/west.h5`. `run.sh` compares the
requested iteration count in `west.cfg` with `west_current_iteration-1` in HDF5.
A normal stop at `max_run_wallclock` (02:00:00) is reported as `paused`, with
the completed count.

Use `./init.sh --reset` only to discard a run and start again. Reset removes
`west.h5`, `west.log`, `traj_segs/`, `seg_logs/`, `istates/` and the
`work/*.tsv` files written by `anal.py`. It checks inputs first and refuses
changed inputs. Start a changed calculation in a new tutorial copy.

If a kill, node failure or scheduler time limit stops `w_run` mid-iteration,
`west.h5` keeps the incomplete segments. Re-running `./run.sh` with the same
inputs propagates only those segments again. Before calling `runseg.sh`, the
WESTPA 2022.15 executable propagator removes and recreates each incomplete
`work/traj_segs/<iteration>/<segment>/` directory. Copy partial AMBER output
elsewhere before the rerun if you need it for diagnosis.

`runseg.sh` stops with `Segment output from an earlier propagation attempt was
kept` when a segment directory already holds output from an earlier attempt.
This happens when the callback runs outside `w_run` or under a WESTPA version
that keeps partial segments. Inspect the files, move the directory to
`<segment>.failed.<timestamp>` with the `mv` command printed in the error, and
rerun `./run.sh`. Interrupting and resuming a real AMBER/WESTPA run has not been
tested.

### Troubleshooting

| Error message | What to check |
| --- | --- |
| `w_init not found. Activate the WESTPA 2 environment.` | Activate the environment where WESTPA is installed. |
| `Run build.sh first: .../bstates/basis.rst7` | Confirm that `build.sh` finished the basis-state equilibration. |
| `An existing WESTPA state was found` | Continue with `./run.sh`; start a new run with `./init.sh --reset`. |
| `AMBER propagation failed with exit status N` | `work/seg_logs/<iteration>-<segment>.log` and `segment.out` in the segment directory |
| `start progress coordinate failed`, `end progress coordinate failed` | `pcoord.start.cpptraj.log` and `pcoord.end.cpptraj.log` in the segment directory; `work/get_pcoord.log` for initial states |
| `WESTPA run failed`, `A run error was recorded in the WESTPA log` | The last 20 lines of `work/west.log` and the newest segment log printed by `run.sh` |

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure,
concurrent-run protection and log locations.
