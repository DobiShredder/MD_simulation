# Chignolin WESTPA–AMBER weighted ensemble

Reference syntax: Amber 2026 and WESTPA 2.

## 한국어

PDB 1UAO Chignolin을 explicit TIP3P water에서 전파하고 residue 2–9의 Cα RMSD를
progress coordinate로 사용합니다. Conventional MD와 같은 unbiased AMBER
dynamics를 실행하지만, WESTPA가 1 ps마다 walker를 RMSD bin에 배치하고
split/merge하여 bin당 walker 수를 조정합니다. Split된 walker의 weight 합과
parent restart는 보존되며 각 child는 서로 다른 Langevin seed로 이어집니다.

RMSD 3.0 Å 이상은 resampling과 target 분석을 연습하기 위한 partially unfolded
state입니다. 20 iterations의 짧은 기본 run에서는 target event가 없을 수 있으며,
event 수나 target weight를 folding/unfolding rate로 해석하지 않습니다.

### Script 역할

| 파일 | 실행 방식 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 직접 실행 | PDB 1UAO → `structure/1UAO.raw.pdb`, checksum |
| `prepare.py` | 직접 실행 | NMR model 1 → `structure/chignolin.pdb` |
| `build.sh` | 직접 실행 | Chignolin PDB → ff19SB/TIP3P topology, RMSD reference와 basis restart |
| `env.sh` | 자동 호출 | WESTPA root, work directory, AMBER/cpptraj executable 설정 |
| `init.sh` | 직접 실행 | Basis/target state → `work/west.h5` |
| `run.sh` | 직접 실행 | WESTPA iterations → segment restart, log와 갱신된 `west.h5` |
| `westpa_scripts/runseg.sh` | WESTPA가 호출 | Parent restart → 1 ps AMBER segment와 두 pcoord 값 |
| `anal.py` | 직접 실행 | Weight, effective walker, RMSD 범위, bin occupancy와 target 진단 TSV |

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./init.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

### 주요 option

`build.sh`는 ff19SB/TIP3P 12 Å box를 만들고 minimization, 100 ps heating과
100 ps NPT equilibration을 거쳐 `work/bstates/basis.rst7`을 생성합니다.
Minimized structure인 `work/common_files/reference.rst7`에 residue 2–9 Cα를
least-squares fit한 RMSD를 Å 단위로 계산합니다. Terminal residue를 제외하면
말단 움직임이 progress coordinate를 지배하는 현상을 줄일 수 있습니다.

`west.cfg`는 bin당 walker 4개와 20 iterations를 사용합니다. RMSD bin은
0–3 Å 구간에서 조밀하게 나뉘고 `[3.0, inf)`가 target bin입니다.
`tstate.file`의 3.25 Å는 이 bin 안의 representative value입니다. Cα RMSD는
서로 다른 unfolded conformation을 같은 값으로 투영할 수 있으므로, 연구용
계산에서는 native contact나 다른 coordinate를 추가하고 binning을 다시
설계합니다.

Target bin에 도달한 walker의 weight는 다음 iteration에서 folded basis state로
recycling됩니다. 따라서 생성된 walker 집합은 equilibrium conformational
ensemble이 아닙니다. 이 tutorial에서는 recycling과 weight 전달을 관찰하는
용도로만 사용합니다.

Segment input의 `irest=1`, `ntx=5`는 parent coordinate와 velocity를 이어받습니다.
`WEST_RAND32`에서 positive Langevin seed를 만들어 split된 walker가 같은
random-number stream을 반복하지 않게 합니다. 기존 `work/west.h5`를 이어서
실행할 때는 `./run.sh`을 다시 실행합니다. 새 run을 시작할 때만
`./init.sh --reset`을 사용합니다.

기본 engine은 한 GPU에서 serial로 실행하는 `pmemd.cuda`입니다. CPU에서
workflow를 확인할 때는 다음처럼 process work manager를 사용할 수 있습니다.

```bash
AMBER_ENGINE=sander \
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=8 \
./run.sh
```

`iteration_summary.tsv`의 total weight는 1에 가까워야 합니다.
`bin_occupancy.tsv`는 iteration별 segment 수와 weight를 보여주며,
`target_events.tsv`는 RMSD 3.0 Å 이상에 도달한 segment를 기록합니다.

## English

This example propagates PDB 1UAO Chignolin in explicit TIP3P water and uses the
Cα RMSD of residues 2–9 as its progress coordinate. AMBER supplies the same
unbiased dynamics used in conventional MD. Every 1 ps, WESTPA bins the walkers
by RMSD and splits or merges them while conserving statistical weight and
continuing from the parent restart.

Run `download.sh`, `prepare.py`, `build.sh`, `init.sh`, `run.sh`, and `anal.py`
in order. The build uses ff19SB, a 12 Å TIP3P box, minimization, 100 ps heating,
and 100 ps NPT equilibration. RMSD is least-squares fitted to the minimized
reference using the Cα atoms of residues 2–9.

The default configuration maintains four walkers per bin for 20 iterations.
The `[3.0, inf)` Å bin is labeled as a partially unfolded target, with 3.25 Å as
an interior representative value. This target is a tutorial diagnostic rather
than a folding definition. A short run may produce no target event, and target
counts or weights are not a folding/unfolding rate estimate. One-dimensional
Cα RMSD can also combine distinct conformations, so production studies need a
system-specific progress coordinate and binning strategy.

Walkers reaching the target transfer their weight to the folded basis state for
recycling in the next iteration. The resulting walkers therefore do not form an
equilibrium conformational ensemble; recycling is retained here as a workflow
and weight-handling exercise.

Segments continue parent coordinates and velocities with `irest=1` and
`ntx=5`. A positive Langevin seed derived from `WEST_RAND32` gives split walkers
independent random streams. Re-run `run.sh` to continue an initialized WESTPA
run; use `init.sh --reset` only to discard it and start again.

The default is serial `pmemd.cuda` on one GPU. CPU checks may set
`AMBER_ENGINE=sander`, `WESTPA_WORK_MANAGER=processes`, and a positive
`WESTPA_WORKERS` count. Analysis reports total weight, effective walker count,
RMSD range, bin occupancy, and target arrivals.
