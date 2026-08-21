# Ratchet MD and umbrella sampling template

## 한국어

Ratchet MD(rMD)로 reaction coordinate가 목표 방향으로 증가하는 pathway를
만들고, ordered first-crossing frame을 umbrella window seed로 사용합니다.
rMD trajectory는 seed 생성에만 사용하며 PMF는 US production에서 계산합니다.

```bash
./build.sh prepared.pdb

cd rmd
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh
```

`build.sh`는 rMD와 모든 umbrella window가 공유하는 topology와 restart를
만듭니다. `rmd/run.sh`는 tutorial과 같은 minimization, heating,
equilibration, PLUMED ABMD command 순서로 pathway를 생성합니다.
`rmd/anal.py`는 seed restart를 만들고 `us/build.sh`가 `windows.tsv`의
`CENTER_A FORCE_KCAL_MOL_A2` row를 window directory로 변환합니다.
`download.sh PDB_ID`는 RCSB source PDB를 수정하지 않고 `structure/`에
받습니다. Protonation, missing atom과 불필요한 chain은 build 전에 사용자가
정리합니다.

`[umbrella]` atom mask는 각각 한 atom을 선택해야 합니다.
`[ratchet_md] target_distance`는 Å로 입력하고 PLUMED `ABMD TO`의 nm로
변환합니다. `kappa`는 PLUMED ABMD의 ρ 정의를 따르며 일반
harmonic distance force constant와 같은 양이 아닙니다.

## English

Ratchet MD generates a target-directed pathway along the configured distance.
Ordered first-crossing frames seed the umbrella windows; only the umbrella
production trajectories are used for the PMF.

The shared `build.sh` creates one topology and restart for rMD and every
window. `rmd/run.sh` follows the tutorial minimization, heating, equilibration,
and PLUMED ABMD command structure. `rmd/anal.py` extracts seed restarts, and
`us/build.sh` converts the two-column `windows.tsv` table into window
directories before `us/run.sh` propagates them.
`download.sh PDB_ID` retrieves an unmodified RCSB PDB into `structure/`;
protonation, missing atoms, and unwanted chains remain user preparation steps.

Each umbrella atom mask must select one atom. `target_distance` is entered in
Å and converted to the PLUMED `ABMD TO` value in nm. `kappa` follows the
PLUMED ABMD ρ definition and is not an ordinary harmonic-distance force
constant.
