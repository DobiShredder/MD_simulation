# Binding energy / End-state 결합 에너지

## 한국어

Trypsin–benzamidine conventional-MD trajectory에서 MMPBSA.py single-trajectory
MM/GBSA와 MM/PBSA를 계산합니다. Explicit solvent trajectory에서 같은 complex,
receptor와 ligand coordinate를 추출해 molecular-mechanics energy와 implicit
solvation energy를 조합합니다.

- [MM/GBSA](6.1_MMGBSA/)
- [MM/PBSA](6.2_MMPBSA/)

두 방법은 configurational entropy를 포함하지 않습니다. 짧은 trajectory의
ΔTOTAL은 절대 binding free energy나 수렴된 affinity가 아니며, force field,
implicit-solvent model, frame selection과 correlated sampling에 의존합니다.

## English

MMPBSA.py applies single-trajectory MM/GBSA and MM/PBSA to the
trypsin–benzamidine simulation. The examples omit configurational entropy and
are end-state model estimates, not converged absolute binding free energies.
