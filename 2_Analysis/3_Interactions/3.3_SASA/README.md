# SASA / 용매 접근 표면적

## 한국어

LCPO algorithm으로 Chignolin 전체 solvent-accessible surface area(SASA)와 각
residue의 기여도를 계산합니다. Probe offset은 AMBER 기본값인 1.4 Å입니다.

```bash
TOPOLOGY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/system.parm7
TRAJECTORY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/production.nc

./run.sh "$TOPOLOGY" "$TRAJECTORY"
python3 anal.py
```

`sasa_total.dat`에는 frame별 protein SASA가, `sasa_byres.dat`에는 residue별
기여도가 Å² 단위로 기록됩니다. `anal.py`는 total time series와 residue별 평균을
표시합니다. Residue 계산에는 `solutemask :1-10`을 사용하므로 각 residue가
분리된 molecule이 아니라 전체 protein에 기여하는 surface를 계산합니다.

LCPO의 부분 selection 기여도는 근사식 때문에 작은 음수가 나올 수 있습니다.
이는 parser failure가 아닙니다. 서로 다른 system이나 ligand-bound state를
비교할 때는 atom mask, radii와 probe offset을 같게 유지합니다.

## English

The LCPO algorithm calculates total Chignolin SASA and residue contributions
with the AMBER-default 1.4 Å probe offset. `anal.py` displays the total time
series and mean residue contributions in Å². `solutemask :1-10` evaluates each
residue in the context of the full protein. Small negative contributions can
occur for partial LCPO selections and are not necessarily parser errors.
