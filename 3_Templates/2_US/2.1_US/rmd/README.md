# Ratchet MD pathway

## 한국어

`run.sh`는 root build의 topology를 재사용해 solvent minimization, whole-system
minimization, heating, equilibration과 ratchet MD를 실행합니다. Generated
input은 `work/inputs/`, PLUMED input은 `work/plumed.dat`에 저장됩니다.

```bash
./run.sh
python3 anal.py
```

`--preparation-only`, `--production-only`, `--dry-run`을 지원합니다.
`equilibration_ensemble = "NPT"`이면 ratchet MD 전에 `work/equil.out`의 마지막
density가 `[ratchet_md]`의 `minimum_density`–`maximum_density`(g/cm³) 범위인지
확인합니다. AMBER는 constant pressure에서만 density를 출력하므로 `NVT`에서는
이 검사를 건너뜁니다. Positional restraint(`ntr=1`)를 쓰는 solvent minimization,
heating, equilibration input에는 AMBER manual 권장에 따라 `&ewald netfrc=0`을
씁니다.
`anal.py`는 `../us/windows.tsv`의 ordered center에 맞는 first-crossing
restart를 `work/seeds/` 아래에 저장합니다.

빈 output도 기존 파일로 취급합니다. Completion marker와 필수 nonempty output이 모두 있어야 단계를 건너뛰며, partial output은 자동으로 덮어쓰지 않습니다.

## English

`run.sh` reuses the shared topology for minimization, heating, equilibration,
and ratchet MD. Generated AMBER inputs are stored under `work/inputs/`, and
the resolved PLUMED input is `work/plumed.dat`. `anal.py` extracts ordered
first-crossing restarts into `work/seeds/`.

With `equilibration_ensemble = "NPT"`, ratchet MD starts only when the last
density in `work/equil.out` lies within `[ratchet_md]` `minimum_density` to
`maximum_density` (g/cm³). AMBER prints density only at constant pressure, so
the check is skipped for `NVT`. Stages with positional restraints (`ntr=1`:
solvent minimization, heating, equilibration) set `&ewald netfrc=0`, as the
AMBER manual recommends.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.
