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
`anal.py`는 `../us/windows.tsv`의 ordered center에 맞는 first-crossing
restart를 `work/seeds/` 아래에 저장합니다.

## English

`run.sh` reuses the shared topology for minimization, heating, equilibration,
and ratchet MD. Generated AMBER inputs are stored under `work/inputs/`, and
the resolved PLUMED input is `work/plumed.dat`. `anal.py` extracts ordered
first-crossing restarts into `work/seeds/`.
