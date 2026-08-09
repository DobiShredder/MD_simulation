# Geometry / 거리·각도·이면각

## 한국어

원자 selection으로 정의한 distance, minimum distance, angle과 backbone
dihedral을 계산합니다. Chignolin의 terminal Cα distance와 residue 1–5–10 Cα
angle은 전체 fold의 간단한 collective variable로 사용합니다.

```bash
TOPOLOGY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/system.parm7
TRAJECTORY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/production.nc

./run.sh "$TOPOLOGY" "$TRAJECTORY"
python3 anal.py
```

`geometry.dat`에는 `:1@CA`–`:10@CA` distance, residue 1–5와 6–10 heavy atom
사이의 minimum distance, Cα angle이 기록됩니다. `phi_psi.dat`에는 residue
2–9의 φ/ψ가 들어갑니다. `anal.py`는 distance와 angle time series 및 residue
5 Ramachandran scatter를 표시합니다. Distance는 Å, angle과 dihedral은 degree
단위입니다.

Atom mask는 물리적으로 추적하려는 group을 반영해야 합니다. Residue 번호만
그대로 둔 채 다른 protein에 적용하지 않습니다. Imaging은 계산 전에 수행하지만
원하는 molecule이 같은 image에 놓였는지도 확인합니다.

## English

The example calculates terminal Cα distance, minimum heavy-atom distance
between two residue groups, a three-Cα angle, and backbone φ/ψ. `anal.py`
shows the time series and a residue-5 Ramachandran scatter. Distances use Å;
angles and dihedrals use degrees. Atom masks define the physical observable
and must be redesigned rather than copied unchanged to another protein.
