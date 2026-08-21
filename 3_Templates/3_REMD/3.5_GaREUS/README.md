# GaREUS template

## 한국어

REUS의 umbrella-state 교환에 system 전체의 dual-boost GaMD를 결합합니다.
한 reference replica에서 만든 `gamd-restart.dat`를 모든 window에 복사하므로
production 시작 시 같은 boost parameter를 사용합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

Reaction-coordinate mask, center, force와 exchange interval은 REUS와 같습니다.
GaMD statistics 길이와 `sigma0=6 kcal/mol`은 `[gamd]`에 기록됩니다. Build는
REUS와 같은 window/restraint generator에 GaMD parameter-preparation input을
추가합니다. Run은 GaMD state continuation과 AMBER `-rem 3` exchange command를
조합합니다. MD restart, window restraint와 GaMD state 중 하나라도 partial이면
production을 덮어쓰지 않습니다.
`download.sh PDB_ID`는 source PDB를 내려받고 `build.sh`는 topology, window와
GaMD input을 생성합니다.

기본 production은 window당 200 ns입니다. 2 fs timestep과 1000-step exchange
interval에서 `nstlim=1000`, `numexchg=100000`으로 생성됩니다.
기본 20개 window는 6–25 Å이며 replica 009에서 공통 GaMD state를 준비합니다.

## English

GaREUS combines umbrella-state exchange with a common system-wide dual GaMD
boost. One reference replica prepares `gamd-restart.dat`, which is copied to
all windows before production. The build extends the shared REUS window
generator with GaMD preparation input, and the run combines GaMD state
continuation with the AMBER `-rem 3` exchange command. Partial production,
restraint, or GaMD state is not overwritten. `download.sh`
retrieves a source PDB and `build.sh` creates the topology, windows, and GaMD
inputs. The default is 200 ns
per window, rendered as `nstlim=1000` and `numexchg=100000` at 2 fs. The
default has 20 windows from 6 to 25 Å and prepares the shared GaMD state in
replica 009.
