# AMBER umbrella windows / AMBER umbrella window

## 한국어

Ratchet MD restart를 6–24 Å umbrella window의 seed로 사용합니다. 모든
window는 같은 `system.parm7`을 사용합니다. `windows.tsv`에는 center(Å)와
AMBER NMR-style `rk2=rk3`(kcal mol⁻¹ Å⁻²)을 기록합니다. 다른 engine의 force
constant를 옮길 때는 energy definition을 확인합니다.

```bash
cd 1_Simulation/2_US/us
./build.sh --dry-run
./build.sh
./run.sh --dry-run --window 1
./run.sh --window 1
./run.sh
```

`build.sh`는 `../rmd/work/seeds/`에서 `work/windows/NNN/`을 만듭니다. 기존
window directory가 있으면 종료합니다. 각 window의 계산 순서는 아래와
같습니다.

1. Distance restraint가 활성화된 minimization
2. Protein heavy-atom restraint와 distance restraint를 사용한 200 ps NVT heating
3. Distance restraint를 사용한 1 ns NPT equilibration
4. Distance restraint를 사용한 10 ns NPT production

`run.sh`는 `.<stage>.complete` marker가 없는 stage부터 실행하고 완료된 window는
건너뜁니다. 정상 종료 시 실행한 window와 기존 완료 window 수를
한 번만 출력합니다. 비정상 종료 후에는 marker와 AMBER output을 같이
확인합니다.
`inputs/continue.in`은 production restart에서 좌표와 velocity를 이어받는
10 ns continuation input입니다.

Production distance는 `distance.dat`에 1 ps 간격으로 기록됩니다. PMF 계산은
equilibration 제거, time correlation, neighboring histogram overlap과 반복
계산을 포함합니다. 기본 production은 window당 10 ns입니다.

## English

Ordered ratchet-MD restart frames seed windows from 6 to 24 Å. Every window
uses the same topology. `windows.tsv` stores the center in Å and AMBER
NMR-style `rk2=rk3` in kcal mol⁻¹ Å⁻². Check the energy definition before
transferring force constants from another engine.

`build.sh` creates `work/windows/NNN/` only after validating every seed and
refuses to overwrite an existing build. Each window runs restrained
minimization, 200 ps NVT heating, 1 ns NPT equilibration, and 10 ns NPT
production. Successful-stage markers allow `run.sh` to resume a partial local
workflow and skip completed windows. The terminal reports only the final count
of processed and previously completed windows. Inspect the marker and AMBER
output after any abnormal termination.

`inputs/continue.in` inherits coordinates and velocities from a production
restart. Production distances are written to `distance.dat` every 1 ps. PMF
analysis covers equilibration removal, time correlation, neighboring overlap,
endpoint coverage, and replicate uncertainty. Production is 10 ns per window.
