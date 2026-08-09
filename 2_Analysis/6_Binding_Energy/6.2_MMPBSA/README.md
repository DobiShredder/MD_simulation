# MM/PBSA

## 한국어

Poisson–Boltzmann equation을 수치적으로 풀어 polar solvation energy를
계산합니다. 같은 frame에서 GB도 함께 계산해 implicit-solvent model에 따른
차이를 확인합니다.

```bash
./run.sh
python3 anal.py
```

Frame, topology와 decomposition 설정은 MM/GBSA tutorial과 같습니다. PB는
`istrng=0.15 M`, `indi=1.0`, `exdi=80.0`, `fillratio=4.0`, `scale=2.0`,
`inp=2`, `radiopt=0`을 사용합니다. `radiopt=0`은 topology의 mbondi2 radii를
사용한다는 뜻입니다.

`anal.py`는 GB와 PB의 energy component, ΔTOTAL running mean, block mean과
residue decomposition을 같은 형식으로 기록합니다. 두 model의 값이 다른 것은
solver failure가 아니며 model dependence를 보여주는 결과입니다.

## English

MM/PBSA numerically solves the Poisson–Boltzmann model and runs GB on the same
frames for comparison. PB uses 0.15 M ionic strength, internal/external
dielectrics 1/80, fill ratio 4, scale 2, and topology mbondi2 radii. Differences
between GB and PB report model dependence, not solver error.
