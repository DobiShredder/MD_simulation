# Hydrogen bonds / 수소 결합

## 한국어

Chignolin 내부 hydrogen bond와 protein–water hydrogen bond를 분리해
계산합니다. Donor–acceptor distance는 3.0 Å 이하, donor–H–acceptor angle은
135° 이상을 사용합니다.

```bash
TOPOLOGY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/system.parm7
TRAJECTORY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/production.nc

./run.sh "$TOPOLOGY" "$TRAJECTORY"
python3 anal.py
```

`run.sh`는 `ProteinHB`와 `WaterHB` action을 실행합니다.
`protein_hbond_count.dat`과 `water_hbond_count.dat`은 frame별 개수를,
`protein_hbond_average.dat`과 `water_hbond_average.dat`은 interaction별 평균을
기록합니다. `water_bridge.dat`에는 둘 이상의 solute residue를 연결한 water가
기록됩니다. `anal.py`는 count와 protein 내부 occupancy 상위 항목을 표시합니다.

`solventdonor :WAT`과 `solventacceptor :WAT@O`는 TIP3P naming에 맞춘 값입니다.
다른 solvent residue나 atom name을 사용하면 두 mask를 바꿉니다. Cutoff를 바꾼
결과는 같은 hydrogen-bond definition을 사용한 결과끼리 비교합니다.

## English

The workflow separates intraprotein and protein–water hydrogen bonds using a
3.0 Å distance and 135° angle criterion. It writes per-frame counts,
interaction averages, binary series, and solvent bridges. `anal.py` displays
counts and the most occupied intraprotein bonds. The water donor and acceptor
masks follow TIP3P naming and must be changed for another solvent model.
