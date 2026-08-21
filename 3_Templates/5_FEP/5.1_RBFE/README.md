# RBFE template

## 한국어

Ligand A에서 ligand B로 변환하는 dual-topology AMBER RBFE window를 complex와
solvent environment에 각각 만듭니다. `build.sh`에는 ligand를 제외한 reviewed
protein PDB를 전달합니다. 서로 같은 coordinate frame에 배치한 precharged MOL2,
matching frcmod와 one-to-one `atom_mapping.tsv`는 `config.toml`에서 지정합니다.

```bash
./build.sh prepared_protein.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

기본 lambda는 0.0–1.0의 11개 state이며 restraint stage는 없습니다. 각 window는
250,000-step heating, 500,000-step equilibration과 10,000,000-step production을
실행합니다. `ifmbar=1`, `bar_intervall=5000`으로 cross-state energy를 기록합니다.
Build는 두 ligand mask가 비어 있지 않고 겹치지 않는지, mapping atom 이름이
각 ligand에 존재하며 one-to-one인지 검사합니다.

Production 일부만 존재하면 자동으로 덮어쓰지 않습니다. `anal.py`는 완료 marker가
있는 모든 production output을 사용하며 FE-ToolKit의
`edgembar-amber2dats.py`와 `edgembar`가 필요합니다.
`download.sh PDB_ID`는 optional source protein PDB를 내려받습니다. `build.sh`는
두 environment와 lambda window를 생성하고, `run.sh`는 window별 stage를
실행하며, `anal.py`는 MBAR free energy와 overlap을 계산합니다.

## English

This dual-topology Amber RBFE template creates complex and solvent windows for
ligand A to ligand B. Pass a ligand-free reviewed protein PDB to `build.sh` and
configure aligned precharged MOL2 files, matching frcmod files, two ligand
masks, and a one-to-one atom-name map. The default schedule contains 11 states;
each window runs 10,000,000 production steps and records cross-state energies
with `ifmbar`. `download.sh` can retrieve a source protein PDB, `build.sh`
creates both environments and their windows, `run.sh` executes them, and
`anal.py` estimates MBAR free energy and overlap. Partial production is not
overwritten automatically. The analysis requires FE-ToolKit
`edgembar-amber2dats.py` and `edgembar` on `PATH`.
