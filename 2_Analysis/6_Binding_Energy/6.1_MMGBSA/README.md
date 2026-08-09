# MM/GBSA

## 한국어

Single-trajectory MM/GBSA는 같은 complex frame에서 receptor와 ligand를
분리합니다. Bonded energy가 상쇄되는 장점이 있지만 unbound ensemble이 bound
conformation과 같다는 가정을 둡니다.

Trypsin–benzamidine conventional MD를 먼저 실행한 뒤 이 directory에서 계산합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 `ante-MMPBSA.py`로 water와 mobile ion을 제거하고 `:BEN`을 ligand로
분리합니다. Receptor에는 trypsin과 structural Ca²⁺가 들어갑니다. Complex,
receptor와 ligand topology는 모두 `mbondi2` PBRadii를 사용합니다.

기본 계산은 1 ns production에서 10 ps 간격으로 저장한 100개 frame에
`igb=5`, `saltcon=0.15 M`와 LCPO nonpolar term을 적용합니다. `idecomp=2`는
per-residue contribution을 기록합니다. `anal.py`는 energy, running mean, 5개
block과 decomposition을 TSV로 요약합니다.

## English

The single-trajectory workflow strips solvent and separates `:BEN` from the
same complex snapshots. It uses mbondi2 radii, GB model 5, 0.15 M salt, LCPO,
and per-residue decomposition for 100 sampled frames. Entropy is omitted.
