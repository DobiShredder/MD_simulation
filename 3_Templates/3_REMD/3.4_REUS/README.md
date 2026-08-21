# REUS template

## 한국어

Reaction coordinate의 각 umbrella center를 replica state로 두고 AMBER
multidimensional replica exchange로 인접 state를 교환합니다. `windows.tsv`에는
center를 Å 단위로 한 줄에 하나씩 적고 `config.toml`에는 두 AMBER atom mask,
force constant와 exchange interval을 지정합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

Build는 두 mask가 각각 한 atom을 선택하는지 확인하고 `work/states.tsv`와
window directory를 만듭니다. AMBER에서는 `nstlim`이 exchange 사이 MD steps,
`numexchg`가 segment의 exchange 횟수입니다. MPI process 수는 window 수와 같아야
하며 `MPI_PROCESSES`, `MPI_OPTIONS`로 실행 환경을 조정합니다.
`download.sh PDB_ID`는 source PDB를 내려받고 `run.sh`는 preproduction과
multidimensional replica exchange를 순서대로 실행합니다.

기본 production은 window당 200 ns입니다. 2 fs timestep과 1000-step exchange
interval에서 input은 `nstlim=1000`, `numexchg=100000`으로 생성됩니다.

## English

Each umbrella center is a replica state. Amber multidimensional replica
exchange swaps neighboring states while every replica samples its harmonic
window. The build resolves two one-atom AMBER masks and writes dynamic states.
`download.sh` retrieves a source PDB, and `run.sh` executes preproduction and
multidimensional replica exchange.
Amber uses `nstlim` for steps between attempts and `numexchg` for attempts per
segment; the MPI process count must equal the number of windows. The default is
200 ns per window, rendered as `nstlim=1000` and `numexchg=100000` at 2 fs.
