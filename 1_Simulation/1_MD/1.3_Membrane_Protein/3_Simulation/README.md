# KcsA AMBER simulation / KcsA AMBER 시뮬레이션

## 한국어

2단계의 `work/system.parm7`과 `work/system.rst7`로 KcsA membrane system을
완화하고 1 ns production을 실행합니다. Sampling은 conventional MD와 같습니다.
Positional restraint는 초기 구조를 완화하는 동안에만 적용합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Input preflight와 두 minimization, heating, equilibration, production을 순서대로 실행합니다. |
| `inputs/min-solvent.in` | Protein·lipid heavy atoms와 filter K+를 restraint하고 water·bulk ions를 minimize합니다. |
| `inputs/min-lipid.in` | Lipid restraint를 풀고 protein heavy atoms와 filter K+를 restraint하며 minimize합니다. |
| `inputs/heat.in` | 200 ps 동안 20→310 K heating을 진행하고 velocity를 생성합니다. |
| `inputs/equil-heavy.in` | Protein heavy atoms와 filter K+를 restraint하는 40 ps NPT equilibration입니다. |
| `inputs/equil-backbone.in` | Protein backbone과 filter K+를 restraint하는 40 ps NPT equilibration입니다. |
| `inputs/equil.in` | 모든 positional restraint를 해제한 20 ps NPT equilibration입니다. |
| `inputs/production.in` | Restraint 없는 1 ns anisotropic NPT production입니다. |

### 실행

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh
~~~

필요한 program과 계산량은 [1_MD README](../../README.md#준비-사항)에 있습니다.
기본 engine은 `pmemd.cuda`이며 `AMBER_ENGINE`으로 바꿉니다.
Production이 완료된 `work`에서 다시 실행하면 engine을 실행하지 않고
`Skipping completed production`을 출력한 뒤 정상 종료합니다.
실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

Solvent → lipid → protein 순서로 초기 구조를 완화합니다. Water와 bulk ions는
처음부터 움직이고, lipid heavy-atom restraint는 첫 minimization 뒤에 풉니다.
Protein은 heavy atoms → backbone → 전체 해제 순서로 진행합니다. Side chains는
backbone stage부터, backbone은 마지막 equilibration부터 positional restraint 없이
움직입니다. Equilibration은 총 50,000 steps(100 ps)이며 20,000 + 20,000 +
10,000 steps로 나눕니다. 기본값은 310 K와 anisotropic pressure coupling입니다.

### 주요 output과 완료 확인

Stage마다 `work/<stage>.out`, `.rst7`, `.info`를 남기고 dynamics stage는 `.nc`도
남깁니다. Frame은 10 ps(`ntwx=5000`)마다 기록하므로 `heat.nc` 20,
`equil-heavy.nc`와 `equil-backbone.nc` 각 4, `equil.nc` 2, `production.nc` 100
frame입니다. 정상 종료하면 terminal 마지막 두 줄이 다음과 같습니다.

~~~text
Completed: 1 ns production (work/production.out)
Production trajectory: work/production.nc
~~~

공통 확인 항목은 [1_MD README](../../README.md#결과-판단)에 있습니다. Membrane
system에서는 trajectory의 box x·y 길이(membrane area)와 z 길이가 한 방향으로 계속
변하지 않는지, filter K+ 7개가 selectivity filter 안에 남는지 함께 봅니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `ntp=2`, `barostat=2` | Monte Carlo barostat로 x·y·z box dimension을 anisotropic하게 조절합니다. |
| `cut=12.0`, `fswitch=10.0` | 모든 stage에서 LJ force를 10→12 Å 사이에서 0으로 줄이고 12 Å에서 direct-space 계산을 자릅니다. Amber26 manual §3.6은 MC barostat와 hard LJ cutoff 조합이 lipid bilayer를 변형할 수 있어 LJ force switch를 권장합니다(Gomez et al., *J. Comput. Chem.* 2022). Sander에서는 `fswitch`가 `vdwmeth=0`(long-range dispersion correction 없음)으로 바뀝니다. Force switch만으로 약 20% 느려지고(manual) 12 Å cutoff는 계산량을 더 늘립니다. `pmemd.cuda` 실행은 미검증입니다. |
| `temp0=310`, `ntt=3`, `gamma_ln=1.0` | 310 K Langevin thermostat 설정입니다. |
| `ntr=1`, `restraint_wt` | Harmonic positional restraint입니다. 두 minimization에서 10, heating에서 5, heavy-atom/backbone equilibration에서 1 kcal·mol⁻¹·Å⁻²를 사용합니다. 마지막 equilibration과 production은 `ntr=0`입니다. |
| `:1-415 & !@H=` | KcsA 408 residues의 heavy atoms와 filter K+ 7개를 선택합니다. |
| `(:1-408 & @N,CA,C,O,OXT) \| :409-415` | Protein backbone heavy atoms와 filter K+를 선택합니다. Lipid나 water의 `O`는 선택하지 않습니다. |
| `&ewald netfrc=0` | Positional restraint를 사용하는 stage에서 인위적인 net-force 제거를 끕니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond SHAKE와 2 fs timestep을 사용합니다. |
| `ntmin=2`, `dx0=0.0001` | 초기 protein side-chain contact를 완화하도록 두 minimization에서 작은 step의 steepest descent만 사용합니다. |

첫 minimization은 위 protein/filter selection과 Lipid21의 `PA,PC,PE,OL,CHL`
heavy atoms를 함께 restraint합니다. `POPC`·`POPE`는 AMBER topology에서 여러
residue로 나뉩니다. Topology residue 순서나 lipid 종류가 바뀌면 각 mask를 수정합니다.
Filter K+는 두 restrained equilibration까지 유지하고 마지막 stage에서 풉니다.

### Restart와 reference

두 minimization의 `-ref`는 최초 `system.rst7`입니다. Heating은
`min-lipid.rst7`에서 velocity를 생성합니다(`irest=0`, `ntx=1`). 이후 stage는 이전
restart의 원자 좌표와 velocity를 읽습니다(`irest=1`, `ntx=5`). Heavy-atom과
backbone equilibration의 `-ref`는 모두 `heat.rst7`이며, backbone stage에서
reference를 새 구조로 바꾸지 않습니다. 마지막 equilibration은 `-ref`를 쓰지 않고
`equil.rst7`을 production에 전달합니다.

각 dynamics 실행의 `ig=-1`은 새 Langevin seed를 선택합니다. Velocity는 이어받지만
난수열을 이어받는 bitwise continuation은 아닙니다.

### 주의

각 input의 step 수를 바꿀 때는 세 equilibration stage의 합계를 확인합니다.
100 ps equilibration과 1 ns production은 실행 연습용 길이이며 membrane 수렴을
보장하지 않습니다. 연구 계산은 membrane area·두께와 protein 상태의 안정성을
확인하면서 더 긴 equilibration과 sampling을 설계합니다.

### 자주 생기는 문제

공통 `run.sh` message는 [1_MD README](../../README.md#자주-생기는-문제)에 있습니다.

| Message | 조치 |
| --- | --- |
| `Run preflight: topology or restart missing: ../2_Topology_Build/work/system.parm7` | 2단계 `run.sh`를 먼저 실행합니다. |
| `Run preflight: copied input differs and was retained` | 실행 뒤 2단계 topology나 `inputs/*.in`이 바뀌었습니다. `mv work work.old` 후 다시 실행합니다. |
| `solvent minimization failed` 또는 `lipid minimization failed` | `min-*.out` 초기 energy에 overflow(`*****`)가 있으면 1단계의 lipid–protein overlap과 2단계 `leap.log`를 다시 확인합니다. |

## English

The stage-2 `work/system.parm7` and `work/system.rst7` are relaxed and followed
by 1 ns production. Sampling remains conventional MD; positional restraints are
used during preparation only.

### File roles

| File | Role |
| --- | --- |
| `run.sh` | Runs the input preflight, two minimizations, heating, equilibration, and production in order. |
| `inputs/min-solvent.in` | Minimize water/bulk ions with protein/lipid heavy atoms and filter K+ restrained. |
| `inputs/min-lipid.in` | Release lipids; minimize with protein heavy atoms and filter K+ restrained. |
| `inputs/heat.in` | Generate velocities and heat from 20 to 310 K over 200 ps. |
| `inputs/equil-heavy.in` | 40 ps NPT with protein heavy atoms and filter K+ restrained. |
| `inputs/equil-backbone.in` | 40 ps NPT with protein backbone and filter K+ restrained. |
| `inputs/equil.in` | 20 ps NPT with all positional restraints removed. |
| `inputs/production.in` | Unrestrained 1 ns anisotropic NPT production. |

### Running

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh
~~~

Required programs and the computational cost are listed in the
[1_MD README](../../README.md#prerequisites). The default engine is
`pmemd.cuda`; `AMBER_ENGINE` overrides it.
Rerunning after a completed production skips the engine, prints
`Skipping completed production`, and exits 0.
See [GUIDE.md appendix](../../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

Solvent, lipids, and protein are relaxed in order. Water and bulk ions move from
the first minimization. Lipid heavy-atom restraints are removed for the second
minimization. Protein restraints progress from heavy atoms to backbone to none:
side chains move freely from the backbone stage, and the backbone from the final
equilibration. Equilibration totals 50,000 steps (100 ps): 20,000 heavy-atom,
20,000 backbone, and 10,000 unrestrained steps. The defaults are 310 K and
anisotropic pressure coupling.

### Main outputs and completion check

Each stage leaves `work/<stage>.out`, `.rst7`, and `.info`; dynamics stages also
write `.nc`. Frames are written every 10 ps (`ntwx=5000`): 20 in `heat.nc`, 4 each
in `equil-heavy.nc` and `equil-backbone.nc`, 2 in `equil.nc`, and 100 in
`production.nc`. A successful run ends with these two lines:

~~~text
Completed: 1 ns production (work/production.out)
Production trajectory: work/production.nc
~~~

General checks are listed in the [1_MD README](../../README.md#judging-the-result).
For the membrane system, also check that the box x/y lengths (membrane area) and
z length in the trajectory do not keep drifting in one direction, and that the
seven filter K+ ions stay in the selectivity filter.

### Key options

| Option | Meaning |
| --- | --- |
| `ntp=2`, `barostat=2` | Anisotropic Monte Carlo pressure coupling of the x, y, and z box dimensions. |
| `cut=12.0`, `fswitch=10.0` | In every stage the LJ force is switched to zero between 10 and 12 Å, and the direct-space sum ends at 12 Å. Amber26 manual §3.6 recommends an LJ force switch because the MC barostat with a hard LJ cutoff can deform lipid bilayers (Gomez et al., *J. Comput. Chem.* 2022). In sander, `fswitch` switches to `vdwmeth=0` (no long-range dispersion correction). The force switch alone costs about 20% (manual), and the 12 Å cutoff adds more. Not yet run with `pmemd.cuda`. |
| `temp0=310`, `ntt=3`, `gamma_ln=1.0` | 310 K Langevin thermostat. |
| `ntr=1`, `restraint_wt` | Harmonic positional restraints: 10 for both minimizations, 5 for heating, and 1 kcal·mol⁻¹·Å⁻² for both restrained equilibration stages. The final equilibration and production use `ntr=0`. |
| `:1-415 & !@H=` | Heavy atoms of the 408 KcsA residues and the seven filter K+ ions. |
| `(:1-408 & @N,CA,C,O,OXT) \| :409-415` | Protein backbone heavy atoms and the filter K+ ions; lipid or water atoms named `O` are excluded. |
| `&ewald netfrc=0` | Disables artificial net-force removal in stages with positional restraints. |
| `ntc=2`, `ntf=2`, `dt=0.002` | SHAKE on bonds to hydrogen with a 2 fs timestep. |
| `ntmin=2`, `dx0=0.0001` | Small-step steepest descent only in both minimizations, to relax initial side-chain contacts. |

The first minimization also restrains Lipid21 `PA,PC,PE,OL,CHL` heavy atoms;
POPC/POPE are split across residues in the AMBER topology. Update every mask for
changed residue ordering or lipid types. Filter K+ restraints end at the
unrestrained equilibration stage.

### Restart and reference

Both minimizations reference the initial `system.rst7`. Heating generates
velocities from `min-lipid.rst7` (`irest=0`, `ntx=1`). Later stages read coordinates
and velocities from the previous restart (`irest=1`, `ntx=5`). Both restrained
equilibration stages use the same `heat.rst7` reference; the backbone stage does
not switch to a new reference. The final stage has no `-ref` and passes
`equil.rst7` to production.

Each dynamics invocation uses `ig=-1` for a new Langevin seed. Velocities are
inherited, but the random-number stream is not a bitwise continuation.

### Cautions

Check the sum of the three equilibration stages when changing step counts. The
100 ps equilibration and 1 ns production are practice durations, not evidence of
membrane convergence. Research runs need longer equilibration and sampling with
checks of membrane area, thickness, and protein-state stability.

### Common problems

Shared `run.sh` messages are listed in the [1_MD README](../../README.md#common-problems).

| Message | Action |
| --- | --- |
| `Run preflight: topology or restart missing: ../2_Topology_Build/work/system.parm7` | Run the stage-2 `run.sh` first. |
| `Run preflight: copied input differs and was retained` | The stage-2 topology or `inputs/*.in` changed after the run started. Run `mv work work.old` and rerun. |
| `solvent minimization failed` or `lipid minimization failed` | If the initial energy in `min-*.out` overflows (`*****`), recheck lipid–protein overlaps from stage 1 and the stage-2 `leap.log`. |
