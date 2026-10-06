# KcsA AMBER simulation / KcsA AMBER 시뮬레이션

## 한국어

2단계의 `work/system.parm7`과 `work/system.rst7`을 input으로 사용합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Input preflight와 두 minimization, heating, equilibration, production을 순서대로 실행합니다. |
| `inputs/min-solvent.in` | Protein·lipid heavy atoms와 filter K+를 restraint하고 water·bulk ions를 minimize합니다. |
| `inputs/min-lipid.in` | Lipid restraint를 풀고 protein heavy atoms와 filter K+를 restraint하며 minimize합니다. |
| `inputs/heat.in` | 20→310 K heating을 진행하고 velocity를 생성합니다. |
| `inputs/equil-heavy.in` | Protein heavy atoms와 filter K+를 restraint하는 40 ps NPT equilibration입니다. |
| `inputs/equil-backbone.in` | Protein backbone과 filter K+를 restraint하는 40 ps NPT equilibration입니다. |
| `inputs/equil.in` | 모든 positional restraint를 해제한 20 ps NPT equilibration입니다. |
| `inputs/production.in` | Restraint 없는 1 ns anisotropic NPT production입니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh
~~~

Solvent → lipid → protein 순서로 초기 구조를 완화합니다. Water와 bulk ions는
처음부터 움직이고, lipid heavy-atom restraint는 첫 minimization 뒤에 풉니다.
Protein은 heavy atoms → backbone → 전체 해제 순서로 진행합니다.
Equilibration은 총 50,000 steps(100 ps)이며 20,000 + 20,000 + 10,000 steps로
나눕니다. 이후 1 ns production을 실행합니다.
기본값은 310 K와 anisotropic pressure coupling입니다.
기본 engine은 `pmemd.cuda`입니다.

Sampling은 conventional MD와 같습니다. Restraint는 초기 구조를 완화하는 동안에만
적용합니다. Protein side chains는 backbone stage부터, backbone은 마지막
equilibration부터 positional restraint 없이 움직입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `ntp=2`, `barostat=2` | Monte Carlo barostat로 x·y·z box dimension을 anisotropic하게 조절합니다. |
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

두 minimization의 `-ref`는 최초 `system.rst7`입니다. Heating은
`min-lipid.rst7`에서 velocity를 생성합니다(`irest=0`, `ntx=1`). 이후 stage는 이전
restart의 원자 좌표와 velocity를 읽습니다(`irest=1`, `ntx=5`). Heavy-atom과
backbone equilibration의 `-ref`는 모두 `heat.rst7`이며, backbone stage에서
reference를 새 구조로 바꾸지 않습니다. 마지막 equilibration은 `-ref`를 쓰지 않고
`equil.rst7`을 production에 전달합니다.
각 dynamics 실행의 `ig=-1`은 새 Langevin seed를 선택합니다. Velocity는 이어받지만
난수열을 이어받는 bitwise continuation은 아닙니다.

각 input의 step 수를 바꿀 때는 세 equilibration stage의 합계를 확인합니다.
100 ps equilibration과 1 ns production은 실행 연습용 길이이며 membrane 수렴을
보장하지 않습니다. 연구 계산은 membrane area·두께와 protein 상태의 안정성을
확인하면서 더 긴 equilibration과 sampling을 설계합니다.

## English

The stage-2 topology and restart are the inputs. Solvent, lipids, and protein are
relaxed in order. Water and bulk ions move from the first minimization. Lipid
heavy-atom restraints are removed for the second minimization. Protein restraints
progress from heavy atoms to backbone to none. Sampling remains conventional MD;
the positional restraints are used during preparation only.

| Input | Role |
| --- | --- |
| `inputs/min-solvent.in` | Minimize water/bulk ions with protein/lipid heavy atoms and filter K+ restrained. |
| `inputs/min-lipid.in` | Release lipids; minimize with protein heavy atoms and filter K+ restrained. |
| `inputs/heat.in` | Generate velocities and heat from 20 to 310 K over 200 ps. |
| `inputs/equil-heavy.in` | 40 ps NPT with protein heavy atoms and filter K+ restrained. |
| `inputs/equil-backbone.in` | 40 ps NPT with protein backbone and filter K+ restrained. |
| `inputs/equil.in` | 20 ps NPT with all positional restraints removed. |
| `inputs/production.in` | Unrestrained 1 ns production. |

Run `./run.sh` from this directory. Equilibration totals 50,000 steps: 20,000
heavy-atom, 20,000 backbone, and 10,000 unrestrained steps at 2 fs. Check the sum
when changing these inputs. `run.sh` executes all stages in the listed order.
`ntp=2` with `barostat=2` enables anisotropic Monte Carlo pressure coupling;
`temp0=310`, `ntt=3` and `gamma_ln=1.0` define the Langevin thermostat. SHAKE
(`ntc=2`, `ntf=2`) permits `dt=0.002` ps. Restraint weights are 10 for both
minimizations, 5 for heating, and 1 kcal·mol⁻¹·Å⁻² for both restrained
equilibration stages; the final equilibration and production use `ntr=0`.
Restrained stages set `netfrc=0` in `&ewald` to disable artificial net-force removal.

`:1-415 & !@H=` selects the 408 KcsA residues and seven filter K+ ions.
`(:1-408 & @N,CA,C,O,OXT) | :409-415` keeps backbone heavy atoms and those ions
restrained while releasing side chains. The first minimization also includes
Lipid21 `PA,PC,PE,OL,CHL` heavy atoms; POPC/POPE are split across residues in
the AMBER topology. Update every mask for changed residue ordering or lipid types.
Filter K+ restraints end at the unrestrained equilibration stage.

Both minimizations reference the initial `system.rst7`. Heating generates
velocities from `min-lipid.rst7` (`irest=0`, `ntx=1`). Later stages read coordinates
and velocities from the previous restart (`irest=1`, `ntx=5`). Both restrained
equilibration stages use the same `heat.rst7` reference. The final stage has no
`-ref` and passes `equil.rst7` to production.
Each dynamics invocation uses `ig=-1` for a new Langevin seed. Velocities are
inherited, but the random-number stream is not a bitwise continuation.
Both minimizations use steepest descent (`ntmin=2`) with `dx0=0.0001` to
relax initial side-chain contacts before dynamics.

The default engine is `pmemd.cuda`; `AMBER_ENGINE` overrides it. The 1 ns
production and 100 ps equilibration are practice durations, not evidence of membrane
convergence. Research runs need longer equilibration/sampling and checks of membrane
area, thickness, and protein-state stability.

### 동시 실행과 input 변경

Coordinate build, topology build와 simulation은 membrane tutorial root 옆의 `.writers/` registry를 공유합니다. 앞 단계의 work를 읽는 동안 그 directory를 다시 생성하는 작업은 거부합니다.

Run은 topology, 최초 coordinate file, stage input과 predecessor restart를 SHA256으로 확인합니다. 변경된 input이나 identity가 없는 기존 결과는 보존하고 거부합니다. 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Coordinate build, topology build and simulation share the `.writers/` registry beside the membrane tutorial root. A downstream reader prevents a builder from rewriting its input directory.

Run checks topology, initial coordinates, stage inputs and predecessor restarts with SHA256. Changed inputs and results without identities are preserved and rejected. Start changed calculations in a new tutorial copy.

Normal exit, command failure and INT/TERM release only the owned lock after child termination is verified. Locks left by SIGKILL or node failure are retained. Inspect the reported lock and its `owner.json` host, PID, command and scopes; confirm through the scheduler and owning host that all writers and children stopped before manually removing only that lock directory. A PID missing locally is not sufficient. Apply the same checks to `.gate/`.

Supported `--dry-run` and `--help` do not create writer or identity files. Do not move active work trees or edit identities to reuse results. Protection was tested on a local filesystem with local child processes; network filesystems, remote MPI and termination of writers on other nodes remain unverified.

### Stage 완료 판정 / Stage completion

Input identity는 입력이 같은지 확인하며 engine의 성공 종료를 증명하지 않습니다.
Runner가 engine의 성공 종료와 필수 output을 확인한 뒤 만든 완료 증거가 있어야
stage를 재사용합니다. Output이 남았지만 완료 증거가 없거나 필수 output이
누락·비어 있으면 기존 결과를 보존하고 중단합니다. 기존 결과를 소급 인증하지
않습니다. 새 계산은 생성된 `work/`를 포함하지 않는 새 tutorial copy에서 시작합니다.
`ntwx=0`인 AMBER stage는 trajectory를 완료 조건으로 요구하지 않습니다.
지원되는 continuation은 기존 restart/state 전달 방식을 따릅니다.

Input identity checks unchanged inputs; it does not prove a successful engine exit.
A stage is reused only with completion evidence written after a successful engine
exit and required-output checks. Outputs without that evidence, or missing/empty
required outputs, are preserved and rejected. Existing results are not certified
retroactively. Start a new tutorial copy without generated `work/` directories for
a new calculation. AMBER stages with `ntwx=0` do not require a trajectory for
completion. Supported continuation retains its existing restart/state handoff.
