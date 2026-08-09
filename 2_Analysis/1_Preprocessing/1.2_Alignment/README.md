# Alignment and stripping / 정렬 및 stripping

## 한국어

Imaging한 trajectory를 첫 frame의 backbone에 least-squares fitting하고 solvent와
ion을 제거합니다. Translation과 rotation을 제거한 RMSD는 내부 구조 변화에
집중할 때 사용합니다.

```bash
TOPOLOGY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/system.parm7
TRAJECTORY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/production.nc

./run.sh "$TOPOLOGY" "$TRAJECTORY"
python3 anal.py
```

`run.sh`는 cpptraj을 실행해 `aligned.nc`, `stripped.parm7`과 `average.pdb`를
만듭니다. `rmsd_before.dat`은 fitting하지 않은 값이고 `rmsd_after.dat`은
`:1-10@CA,C,N` fitting 뒤의 값입니다. `anal.py`는 두 RMSD를 비교합니다.

`strip :WAT,Na+,Cl-`는 이 example의 solvent와 ion 이름에 맞춘 mask입니다.
다른 water model이나 ion residue name을 사용할 때는 strip mask를 바꿉니다.
`aligned.nc`와 `stripped.parm7`은 atom 수와 순서가 같으므로 함께 사용합니다.

## English

The trajectory is imaged, fitted to the first-frame backbone, and stripped of
water and ions. `run.sh` creates `aligned.nc`, `stripped.parm7`, and an average
structure. `anal.py` compares RMSD before and after fitting. Update both the
fit mask and solvent/ion names when adapting the input to another system, and
use the stripped topology with the stripped trajectory.
