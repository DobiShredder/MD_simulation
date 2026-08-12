# Chignolin conventional MD / Chignolin 일반 MD

## 한국어

PDB 1UAO의 첫 NMR model로 10-residue chignolin system을 만듭니다.
Force field는 ff19SB, water model은 TIP3P입니다.
계산은 minimization, 200 ps heating, 100 ps NPT equilibration 및 1 ns production 순으로 진행됩니다.

Conventional MD에서는 모든 원자가 같은 physical Hamiltonian과 bath temperature를 따릅니다.
이 작은 protein 예제는 구조 준비, explicit-solvent build와 initial/restart input의 차이를 배우는 기준 workflow입니다.


### Script 역할

| 파일 | 역할 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 1UAO PDB와 mmCIF download 및 checksum 기록 | `structure/1UAO.raw.pdb`, `1UAO.cif`, `SHA256SUMS` |
| `prepare.py` | 첫 NMR model과 허용된 alternate location 선택 | raw PDB → `structure/chignolin.pdb` |
| `build.sh` | ff19SB/TIP3P solvation, neutralization과 topology build | prepared PDB → `work/system.parm7`, `system.rst7`, `system.pdb` |
| `run.sh` | minimization부터 production까지의 계산 실행 | topology/restart → `work/*.out`, `*.rst7`, `*.nc` |

~~~bash
cd 1_Simulation/1_MD/1.1_Soluble_Protein
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh --dry-run
./run.sh
~~~

### 주요 option

| Option | 의미 |
| --- | --- |
| `nstlim`, `dt=0.002` | simulation의 길이를 정합니다. SHAKE를 사용하므로 timestep은 2 fs입니다. |
| `ntt=3`, `gamma_ln=1.0` | Langevin thermostat와 collision frequency를 설정합니다. |
| `ntb=2`, `ntp=1`, `barostat=2` | Equilibration과 production에서 isotropic NPT와 Monte Carlo barostat을 사용합니다. |
| `ntc=2`, `ntf=2` | 수소가 포함된 bond를 SHAKE로 고정하고 해당 bond force 계산을 생략합니다. |
| `restraintmask` | Heating과 equilibration에서 solvent와 ion을 제외한 protein heavy atom을 restraint합니다. |
| `irest`, `ntx` | Heating은 새 velocity를 만들고 이후 stage는 restart의 좌표와 velocity를 읽습니다. |

`structure/SHA256SUMS`에 PDB와 mmCIF checksum이 기록됩니다.
`build.sh`는 `work/system.parm7`과 `work/system.rst7`을 만듭니다.
`work/leap.log`에서 unknown residue, missing atom과 net charge를 확인합니다.

Terminal state, protonation state, disulfide bond의 존재 유무 등은 build 전에 확인합니다.
Heating에서 새 velocity를 만들고 이후 단계는 restart의 좌표와 velocity를 이어받습니다.
기본 engine은 `pmemd.cuda`이며 다른 실행 파일은 `AMBER_ENGINE`으로 지정합니다.
1 ns production 결과는 folding equilibrium이나 수렴 판단에 사용하지 않습니다.



## English

The first NMR model of PDB 1UAO is built with ff19SB and TIP3P. The workflow runs
minimization, 200 ps heating, 100 ps NPT equilibration, and 1 ns production.

Conventional MD propagates one physical Hamiltonian at one bath temperature.
This small protein provides a baseline for structure preparation, explicit
solvation, and the distinction between initial and continuation inputs.

### Script roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads the 1UAO PDB/mmCIF files and records checksums. |
| `prepare.py` | Selects the first NMR model and supported alternate locations. |
| `build.sh` | Builds the solvated ff19SB/TIP3P topology and restart. |
| `run.sh` | Runs minimization, heating, equilibration, and production. |

Key controls are `nstlim`/`dt` for stage length, `ntt=3` and `gamma_ln=1.0`
for Langevin temperature control, `ntb=2`, `ntp=1`, and `barostat=2` for
isotropic NPT, and `ntc=2`/`ntf=2` for SHAKE. Heating creates velocities;
later stages use `irest=1`, `ntx=5` to continue coordinates and velocities.

Check `structure/SHA256SUMS`, terminal states, protonation, and `work/leap.log`.
`build.sh` writes `work/system.parm7` and `work/system.rst7`. Heating creates
velocities, and later stages continue from the restart. `run.sh` uses
`pmemd.cuda`; `AMBER_ENGINE` overrides it.
The 1 ns trajectory is not a folding-equilibrium or convergence result.

## References / 참고 자료

- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)
