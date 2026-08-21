# Funnel-MetaD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Ligand COM의 funnel-axis projection `fps.lp`에 WT-MetaD bias를 쌓고 transverse
distance `fps.ld`를 funnel restraint로 제한합니다. Bulk solvent 전체를 bias하지
않으면서 binding/unbinding 방향을 sampling하는 구성입니다.

```bash
./build.sh prepared-complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`ligand/ligand.mol2`와 `ligand/ligand.frcmod`는 config의 residue name과 net charge가
반영된 precharged GAFF2 input이어야 합니다. Template는 RESP charge를 다시
계산하지 않습니다. Complex PDB의 ligand residue name과 MOL2 template가 같아야
합니다.

`funnel_selection`의 protein/ligand/alignment mask, anchor atom과 두 axis point의
AMBER mask를 system에 맞게 지정합니다. Axis point의 각 mask는 atom 하나를
선택합니다. `build.sh`가 mask를 topology atom number로 변환하고 initial ligand
COM이 configured funnel 안에 있는지 검사합니다.
`download.sh PDB_ID`는 optional source complex를 내려받으며 ligand parameter를
생성하지 않습니다. `run.sh`는 누적 bias state를 이어받고 `anal.py`는 COLVAR와
free-energy reconstruction을 처리합니다.

기본 geometry는 `ZCC=1.8 nm`, `ALPHA=0.55 rad`, cylinder radius 0.1 nm와
35,100 kJ/mol/nm² wall입니다. Hill은 1.2 kJ/mol, sigma 0.05 nm,
`PACE=500`, `BIASFACTOR=10`입니다. 이 값과 20 Å solvent padding은 system 크기와
최대 projection에 맞게 확인합니다.

10 production segments는 root의 `HILLS`, `COLVAR`와 `FUNNEL_GRID`를 공유합니다.
Partial segment는 자동 삭제하지 않습니다. `anal.py --skip-fes`는 hill
reconstruction 없이 projection, transverse distance와 bias 범위만 기록합니다.

## English

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

Funnel-MetaD biases the ligand-COM projection `fps.lp` and confines transverse
motion `fps.ld` with a funnel restraint. Supply a precharged GAFF2 MOL2/frcmod
pair and a complex PDB with the same ligand residue name. RESP charges are not
recomputed.

All masks, the anchor, and both axis-point selections are system-specific.
Each axis mask must select one atom. The build resolves atom numbers and checks
that the initial ligand COM lies inside the configured funnel. The default uses
a 1.2 kJ/mol hill, 0.05 nm sigma, 500-step pace, bias factor 10, and a
35,100 kJ/mol/nm² wall. Segments share root-level `HILLS`, `COLVAR`, and
`FUNNEL_GRID` state. `download.sh` retrieves only a source complex; `build.sh`,
`run.sh`, and `anal.py` create, propagate, and analyze the configured workflow.
