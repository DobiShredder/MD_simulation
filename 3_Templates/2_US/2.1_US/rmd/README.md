# Ratchet MD pathway

## 한국어

Root build의 topology로 ratchet MD pathway를 만들고 umbrella window seed를 추출합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 solvent minimization, whole-system minimization, heating, equilibration과
ratchet MD를 실행합니다. Generated input은 `work/inputs/`, PLUMED input은
`work/plumed.dat`에 저장됩니다. `--preparation-only`는 equilibration까지 실행하고,
`--production-only`는 완료된 equilibration output에서 ratchet MD만 실행합니다.
`--dry-run`은 계획한 command만 출력합니다.

`anal.py`는 `umbrella.windows_file`(기본 `us/windows.tsv`)의 ordered center에 맞는
first-crossing restart를 `work/seeds/` 아래에 저장합니다.

기본값에서 `work/ratchet.nc`와 `work/ratchet.dat`는 `output_interval_steps`(500 steps, 1 ps)마다
기록되어 ratchet.nc는 1,000 frame입니다.
정상 종료하면 `run.sh`와 `anal.py`의 마지막 줄이 각각 다음과 같습니다.

```text
Ratchet-MD trajectory: work/ratchet.nc
Created 19 US seed restarts: work/seeds
```

`equilibration_ensemble = "NPT"`이면 ratchet MD 전에 `work/equil.out`의 마지막
density가 `[ratchet_md]`의 `minimum_density`–`maximum_density`(g/cm³) 범위인지
확인합니다. AMBER는 constant pressure에서만 density를 출력하므로 `NVT`에서는
이 검사를 건너뜁니다. Positional restraint(`ntr=1`)를 쓰는 solvent minimization,
heating, equilibration input에는 AMBER manual 권장에 따라 `&ewald netfrc=0`을
씁니다.

실행 상태와 재실행은 [GUIDE.md 부록](../../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

`run.sh` uses the shared root-build topology to generate the ratchet-MD pathway,
and `anal.py` extracts umbrella-window seeds.

```bash
./run.sh
python3 anal.py
```

`run.sh` runs solvent minimization, whole-system minimization, heating,
equilibration, and ratchet MD. Generated AMBER inputs are stored under
`work/inputs/`, and the resolved PLUMED input is `work/plumed.dat`.
`--preparation-only` stops after equilibration, `--production-only` runs only
ratchet MD from completed equilibration output, and `--dry-run` prints the
planned commands.

`anal.py` writes first-crossing restarts for the ordered centers in
`umbrella.windows_file` (default `us/windows.tsv`) under `work/seeds/`.

By default, `work/ratchet.nc` and `work/ratchet.dat` are both written every
`output_interval_steps` (500 steps, 1 ps), giving 1,000 frames in ratchet.nc. On success, `run.sh` and `anal.py`
end with these lines, respectively:

```text
Ratchet-MD trajectory: work/ratchet.nc
Created 19 US seed restarts: work/seeds
```

With `equilibration_ensemble = "NPT"`, ratchet MD starts only when the last
density in `work/equil.out` lies within `[ratchet_md]` `minimum_density` to
`maximum_density` (g/cm³). AMBER prints density only at constant pressure, so
the check is skipped for `NVT`. Stages with positional restraints (`ntr=1`:
solvent minimization, heating, equilibration) set `&ewald netfrc=0`, as the
AMBER manual recommends.

See [GUIDE.md appendix](../../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state and reruns.
