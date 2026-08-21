# ABFE template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Ligand restraint coupling, complex/solvent charge decoupling과 vdW decoupling을
포함하는 double-decoupling ABFE window를 만듭니다. `build.sh`에는 ligand가
포함된 reviewed complex PDB를 전달하며, 같은 residue name과 atom name을 가진
precharged MOL2와 frcmod를 config에서 지정합니다.

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

세 protein anchor와 세 ligand anchor는 각각 정확히 한 atom을 선택해야 하며 서로
달라야 합니다. Build는 초기 구조에서 1 distance, 2 angle, 3 torsion reference를
계산합니다. Restraint/charge는 11-state schedule, vdW는 16-state schedule을
사용해 총 65개 window를 만듭니다. 기본 force constant는 distance 5
kcal/mol/Å², angle/torsion 100 kcal/mol/rad²이고 standard state는 1 M, 300 K입니다.

각 window production은 10,000,000 steps이며 `bar_intervall=5000`으로 MBAR
energy를 기록합니다. Partial production은 자동으로 덮어쓰지 않습니다.
`download.sh PDB_ID`는 optional source complex를 내려받습니다. `build.sh`는
double-decoupling system과 65개 window를 만들고, `run.sh`는 stage를 실행하며,
`anal.py`는 FE-ToolKit의 `edgembar-amber2dats.py`와 `edgembar`를 사용해
restraint correction과 각 alchemical contribution을 합산합니다.

## English

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This double-decoupling ABFE template includes restraint coupling and charge/vdW
decoupling in complex and solvent environments. Pass a reviewed complex PDB and
configure a matching precharged ligand MOL2/frcmod plus six distinct one-atom
anchor masks. The build creates 65 windows: 11 restraint, 22 charge, and 32 vdW
states. Each window runs 10,000,000 production steps and records MBAR energies
every 5,000 steps. `download.sh` can retrieve a source complex, `build.sh`
creates the double-decoupling systems and windows, `run.sh` executes them, and
`anal.py` combines the alchemical terms and restraint correction. Partial
production is preserved. FE-ToolKit `edgembar-amber2dats.py` and `edgembar`
must be available on `PATH` for analysis.
